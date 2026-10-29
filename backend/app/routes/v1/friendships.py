"""Friendship routes: the rules for sending, answering, removing and blocking, and the endpoints that call them."""

from sqlalchemy.orm import Session

from app.crud.friendship import ErrorCreatingFriendship, create_friendship, read_friendship
from app.db.models import Block, Friendship, User


class NotFound(Exception):
    """Nothing to act on: no such user or request, or a block the caller must not learn about."""


class NotAllowed(Exception):
    """The target exists, but a friendship rule refuses this action."""


def check_not_blocked(session: Session, me_id: int, them_id: int) -> None:
    """Raise NotAllowed if I blocked them, NotFound if they blocked me; return if there is no block."""
    if session.get(Block, (me_id, them_id)) is not None:
        raise NotAllowed("unblock first")
    if session.get(Block, (them_id, me_id)) is not None:
        raise NotFound


def send_request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
    """Ask another user to be friends; the pair's history decides the result. Never commits."""
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
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != them_id:
        raise NotFound
    row.status = "accepted"
    session.flush()
    return row

def decline_request(session: Session, me_id: int, them_id: int) -> None:
    """Decline the pending request they sent me, keeping the row so only I can reopen it; NotFound if there is none. Never commits."""
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != them_id:
        raise NotFound
    row.status = "declined"
    session.flush()

def cancel_request(session: Session, me_id: int, them_id: int) -> None:
    """Withdraw the pending request I sent, deleting the row so either of us can ask again; NotFound if there is none. Never commits."""
    check_not_blocked(session, me_id, them_id)
    row = read_friendship(session, me_id, them_id)
    if row is None or row.status != "pending" or row.requester_id != me_id:
        raise NotFound
    session.delete(row)
    session.flush()

def remove_friend(session: Session, me_id: int, them_id: int) -> None:
    """End our friendship from either side, deleting the row so either of us can ask again; NotFound if we are not friends. Never commits."""
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

    target = session.get(User, them_id)
    if target is None or target.deleted_at is not None:
        raise NotFound
    if session.get(Block, (me_id, them_id)) is not None:
        return

    row = read_friendship(session, me_id, them_id)
    if row is not None:
        session.delete(row)
    session.add(Block(blocker_id=me_id, blocked_id=them_id))
    session.flush()

def unblock_user(session: Session, me_id: int, them_id: int) -> None:
    """Lift my block on them; we are strangers again. NotFound if I have not blocked them. Never commits."""
    block = session.get(Block, (me_id, them_id))
    if block is None:
        raise NotFound
    session.delete(block)
    session.flush()
