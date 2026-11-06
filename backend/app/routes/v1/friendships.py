"""Friendship routes: the rules for sending, answering, removing and blocking, and the endpoints that call them."""

from contextlib import contextmanager

from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.current_user import current_user
from app.crud.friendship import ErrorCreatingFriendship, create_friendship, list_friends, list_pending, read_friendship
from app.db import get_session
from app.db.models import Block, Friendship, User


class NotFound(Exception):
    """Nothing to act on: no such user or request, or a block the caller must not learn about."""


class NotAllowed(Exception):
    """The target exists, but a friendship rule refuses this action."""


def check_exists(session: Session, them_id: int) -> None:
    """Raise NotFound if they never existed or deleted their account; a deleted account is gone for everyone."""
    them = session.get(User, them_id)
    if them is None or them.deleted_at is not None:
        raise NotFound


def check_not_blocked(session: Session, me_id: int, them_id: int) -> None:
    """Raise NotAllowed if I blocked them, NotFound if they blocked me; return if there is no block."""
    if session.get(Block, (me_id, them_id)) is not None:
        raise NotAllowed("unblock first")
    if session.get(Block, (them_id, me_id)) is not None:
        raise NotFound


def send_request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
    """Ask another user to be friends; the pair's history decides the result. Never commits."""
    check_exists(session, addressee_id)
    check_not_blocked(session, requester_id, addressee_id)

    existing = read_friendship(session, requester_id, addressee_id)
    if existing is not None:
        they_asked_first = existing.requester_id == addressee_id
        if existing.status == "declined" and not they_asked_first:
            raise NotAllowed("declined; only the person who said no can ask again")
        if existing.status == "declined":
            # The one who said no changed their mind: same row, roles swapped.
            existing.requester_id, existing.addressee_id = requester_id, addressee_id
            existing.status = "pending"
            session.flush()
            return existing
        if they_asked_first and existing.status == "pending":
            existing.status = "accepted"
            session.flush()
        return existing

    try:
        request = create_friendship(session, requester_id, addressee_id)
    except ErrorCreatingFriendship:
        raise NotFound from None
    if request is None:
        return send_request(session, requester_id, addressee_id)
    return request

def accept_request(session: Session, me_id: int, them_id: int) -> Friendship:
    """Accept the pending request they sent me; NotFound if there is none. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != them_id:
        raise NotFound
    row.status = "accepted"
    session.flush()
    return row

def decline_request(session: Session, me_id: int, them_id: int) -> None:
    """Decline the pending request they sent me, keeping the row so only I can reopen it; NotFound if there is none. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != them_id:
        raise NotFound
    row.status = "declined"
    session.flush()

def cancel_request(session: Session, me_id: int, them_id: int) -> None:
    """Withdraw the pending request I sent, deleting the row so either of us can ask again; NotFound if there is none. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != me_id:
        raise NotFound
    session.delete(row)
    session.flush()

def remove_friend(session: Session, me_id: int, them_id: int) -> None:
    """End our friendship from either side, deleting the row so either of us can ask again; NotFound if we are not friends. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "accepted":
        raise NotFound
    session.delete(row)
    session.flush()

def block_user(session: Session, me_id: int, them_id: int) -> None:
    """Block them and delete any friendship row between us; blocking again changes nothing. NotAllowed on myself, NotFound if they do not exist. Never commits."""
    if me_id == them_id:
        raise NotAllowed

    check_exists(session, them_id)
    if session.get(Block, (me_id, them_id)) is not None:
        return

    row = read_friendship(session, me_id, them_id)
    if row is not None:
        session.delete(row)
    session.add(Block(blocker_id=me_id, blocked_id=them_id))
    session.flush()

def unblock_user(session: Session, me_id: int, them_id: int) -> None:
    """Lift my block on them; we are strangers again. NotFound if I have not blocked them or they are gone. Never commits."""
    check_exists(session, them_id)
    block = session.get(Block, (me_id, them_id))
    if block is None:
        raise NotFound
    session.delete(block)
    session.flush()

router = APIRouter()


@contextmanager
def rule_errors(session: Session):
    """Run a rule inside a with block: NotFound becomes 404, NotAllowed becomes 409, and the session commits only if the block raised nothing."""
    try:
        yield
    except NotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found") from None
    except NotAllowed as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from None
    session.commit()


@router.get("")
def friends(me: User = Depends(current_user), session: Session = Depends(get_session)) -> list[dict]:
    """My friends as id and display name; 401 without a login."""
    return [{"id": friend.id, "display_name": friend.profile.display_name} for friend in list_friends(session, me.id)]

@router.get("/requests")
def requests(me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Pending requests: incoming sent to me, outgoing sent by me."""
    incoming, outgoing = list_pending(session, me.id)
    return {
        "incoming": [{"id": user.id, "display_name": user.profile.display_name} for user in incoming],
        "outgoing": [{"id": user.id, "display_name": user.profile.display_name} for user in outgoing],
    }

@router.post("/request/{them_id}")
def request(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Ask them to be friends; 200 with the resulting status, 422 on myself, 404 if there is nothing to ask, 409 if a rule refuses."""
    if me.id == them_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
    with rule_errors(session):
        friendship = send_request(session, me.id, them_id)
    return {"status": friendship.status}

@router.post("/accept/{them_id}")
def accept(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Accept the pending request they sent me; 200 accepted, 422 on myself, 404 if they sent me none, 409 if I blocked them."""
    if me.id == them_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
    with rule_errors(session):
        accept_request(session, me.id, them_id)
    return {"status": "accepted"}

@router.post("/decline/{them_id}")
def decline(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Decline the pending request they sent me; 200 declined, 422 on myself, 404 if they sent me none, 409 if I blocked them."""
    if me.id == them_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
    with rule_errors(session):
        decline_request(session, me.id, them_id)
    return {"status": "declined"}

@router.post("/cancel/{them_id}")
def cancel(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Withdraw the pending request I sent them; 200 cancelled, 422 on myself, 404 if I sent them none, 409 if I blocked them."""
    if me.id == them_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
    with rule_errors(session):
        cancel_request(session, me.id, them_id)
    return {"status": "cancelled"}

@router.delete("/{them_id}")
def remove(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """End our friendship from either side; 200 removed, 422 on myself, 404 if we are not friends, 409 if I blocked them."""
    if me.id == them_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
    with rule_errors(session):
        remove_friend(session, me.id, them_id)
    return {"status": "removed"}

@router.post("/block/{them_id}")
def block(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Block them and drop any friendship between us, again is a no-op; 200 blocked, 422 on myself, 404 if they do not exist."""
    if me.id == them_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
    with rule_errors(session):
        block_user(session, me.id, them_id)
    return {"status": "blocked"}

@router.post("/unblock/{them_id}")
def unblock(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Lift my block on them; 200 unblocked, 422 on myself, 404 if I have not blocked them."""
    if me.id == them_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot act on yourself")
    with rule_errors(session):
        unblock_user(session, me.id, them_id)
    return {"status": "unblocked"}
