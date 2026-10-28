"""Friend requests: what happens when one user asks another to be friends.

The friendships table holds one row per pair of users, so a request first looks
for that pair's row and decides from its state. The route layer calls this and
turns FriendRequestNotAllowed into an error response.
"""

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.db.models import Friendship, User


class FriendRequestNotAllowed(Exception):
    """The pair's history forbids this request (declined by them, or blocked)."""


def _pair_row(session: Session, a: int, b: int) -> Friendship | None:
    """The friendships row for this pair of users, whichever of the two asked."""
    return session.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == a, Friendship.addressee_id == b),
                and_(Friendship.requester_id == b, Friendship.addressee_id == a),
            )
        )
    )


def send_friend_request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
    """Ask another user to be friends; the pair's history decides the result. Never commits."""
    existing = _pair_row(session, requester_id, addressee_id)
    if existing is not None:
        they_asked_first = existing.requester_id == addressee_id
        if existing.status == "blocked":
            raise FriendRequestNotAllowed("blocked")
        if existing.status == "declined" and not they_asked_first:
            raise FriendRequestNotAllowed("declined; only the person who said no can ask again")
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

    request = Friendship(requester_id=requester_id, addressee_id=addressee_id)
    session.flush()  # keep: the caller's pending errors must not be blamed on this insert
    try:
        with session.begin_nested():
            session.add(request)
    except IntegrityError:
        if _pair_row(session, requester_id, addressee_id) is not None:
            return send_friend_request(session, requester_id, addressee_id)
        raise FriendRequestNotAllowed("cannot ask yourself or a user who does not exist") from None
    return request


def are_friends(session: Session, a: int, b: int) -> bool:
    """True only when the pair's row is accepted; the order of a and b does not matter."""
    row = _pair_row(session, a, b)
    if row is None:
        return False
    return row.status == "accepted"


def list_friends(session: Session, user_id: int) -> list[User]:
    """The user's accepted friends from either side of the pair, deleted accounts left out, ordered by id."""
    friend = aliased(User)
    return list(session.scalars(
        select(friend)
        .join(Friendship, or_(
            and_(Friendship.requester_id == user_id, Friendship.addressee_id == friend.id),
            and_(Friendship.requester_id == friend.id, Friendship.addressee_id == user_id),
        ))
        .where(Friendship.status == "accepted", friend.deleted_at.is_(None))
        .order_by(friend.id)
    ))
