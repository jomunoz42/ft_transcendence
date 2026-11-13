"""Friendship routes: the rules for sending, answering, removing and blocking, and the endpoints that call them."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.auth.current_user import current_user
from app.crud.friendship import create_friendship, list_friends, list_pending, read_friendship
from app import errors
from app.db import get_session, commit_session
from app.db.models import Block, Friendship, User

def check_exists(session: Session, them_id: int) -> None:
    """Raise 404 if they never existed or deleted their account."""
    them = session.get(User, them_id)
    if them is None or them.deleted_at is not None:
        raise errors.HTTP_404_NOT_FOUND


def check_not_blocked(session: Session, me_id: int, them_id: int) -> None:
    """Raise 409 if I blocked them, 404 if they blocked me."""
    if session.get(Block, (me_id, them_id)) is not None:
        raise errors.HTTP_409_CONFLICT_UNBLOCK_FIRST
    if session.get(Block, (them_id, me_id)) is not None:
        raise errors.HTTP_404_NOT_FOUND


def send_request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
    """Ask another user to be friends; the pair's history decides the result. Never commits."""
    check_exists(session, addressee_id)
    check_not_blocked(session, requester_id, addressee_id)

    existing = read_friendship(session, requester_id, addressee_id)
    if existing is not None:
        they_asked_first = existing.requester_id == addressee_id
        if existing.status == "declined" and not they_asked_first:
            raise errors.HTTP_409_CONFLICT_ONLY_BLOCKER_CAN
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
    except Exception:
        raise errors.HTTP_404_NOT_FOUND from None
    if request is None:
        return send_request(session, requester_id, addressee_id)
    return request

def accept_request(session: Session, me_id: int, them_id: int) -> Friendship:
    """Accept the pending request they sent me. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != them_id:
        raise errors.HTTP_404_NOT_FOUND
    row.status = "accepted"
    session.flush()
    return row

def decline_request(session: Session, me_id: int, them_id: int) -> None:
    """Decline the pending request they sent me, keeping the row so only I can reopen it. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != them_id:
        raise errors.HTTP_404_NOT_FOUND
    row.status = "declined"
    session.flush()

def cancel_request(session: Session, me_id: int, them_id: int) -> None:
    """Withdraw the pending request I sent, deleting the row so either of us can ask again. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != me_id:
        raise errors.HTTP_404_NOT_FOUND
    session.delete(row)
    session.flush()

def remove_friend(session: Session, me_id: int, them_id: int) -> None:
    """End our friendship from either side, deleting the row so either of us can ask again. Never commits."""
    check_exists(session, them_id)
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "accepted":
        raise errors.HTTP_404_NOT_FOUND
    session.delete(row)
    session.flush()

def block_user(session: Session, me_id: int, them_id: int) -> None:
    """Block them and delete any friendship row between us; blocking again changes nothing. Never commits."""
    if me_id == them_id:
        raise errors.HTTP_409_CONFLICT

    check_exists(session, them_id)
    if session.get(Block, (me_id, them_id)) is not None:
        return

    row = read_friendship(session, me_id, them_id)
    if row is not None:
        session.delete(row)
    session.flush()
    try:
        with session.begin_nested():
            session.add(Block(blocker_id=me_id, blocked_id=them_id))
    except IntegrityError:
        if session.get(Block, (me_id, them_id)) is None:
            raise

def unblock_user(session: Session, me_id: int, them_id: int) -> None:
    """Lift my block on them; we are strangers again. Never commits."""
    check_exists(session, them_id)
    block = session.get(Block, (me_id, them_id))
    if block is None:
        raise errors.HTTP_404_NOT_FOUND
    session.delete(block)
    session.flush()


router = APIRouter(dependencies=[Depends(commit_session)])


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
        raise errors.HTTP_422_UNPROCESSABLE_CONTENT
    friendship = send_request(session, me.id, them_id)
    return {"status": friendship.status}

@router.post("/accept/{them_id}")
def accept(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Accept the pending request they sent me; 200 accepted, 422 on myself, 404 if they sent me none, 409 if I blocked them."""
    if me.id == them_id:
        raise errors.HTTP_422_UNPROCESSABLE_CONTENT
    accept_request(session, me.id, them_id)
    return {"status": "accepted"}

@router.post("/decline/{them_id}")
def decline(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Decline the pending request they sent me; 200 declined, 422 on myself, 404 if they sent me none, 409 if I blocked them."""
    if me.id == them_id:
        raise errors.HTTP_422_UNPROCESSABLE_CONTENT
    decline_request(session, me.id, them_id)
    return {"status": "declined"}

@router.post("/cancel/{them_id}")
def cancel(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Withdraw the pending request I sent them; 200 cancelled, 422 on myself, 404 if I sent them none, 409 if I blocked them."""
    if me.id == them_id:
        raise errors.HTTP_422_UNPROCESSABLE_CONTENT
    cancel_request(session, me.id, them_id)
    return {"status": "cancelled"}

@router.delete("/{them_id}")
def remove(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """End our friendship from either side; 200 removed, 422 on myself, 404 if we are not friends, 409 if I blocked them."""
    if me.id == them_id:
        raise errors.HTTP_422_UNPROCESSABLE_CONTENT
    remove_friend(session, me.id, them_id)
    return {"status": "removed"}

@router.post("/block/{them_id}")
def block(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Block them and drop any friendship between us, again is a no-op; 200 blocked, 422 on myself, 404 if they do not exist."""
    if me.id == them_id:
        raise errors.HTTP_422_UNPROCESSABLE_CONTENT
    block_user(session, me.id, them_id)
    return {"status": "blocked"}

@router.post("/unblock/{them_id}")
def unblock(them_id: int, me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    """Lift my block on them; 200 unblocked, 422 on myself, 404 if I have not blocked them."""
    if me.id == them_id:
        raise errors.HTTP_422_UNPROCESSABLE_CONTENT
    unblock_user(session, me.id, them_id)
    return {"status": "unblocked"}
