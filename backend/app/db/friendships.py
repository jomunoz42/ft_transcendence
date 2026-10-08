"""Friend requests: what happens when one user asks another to be friends.

The friendships table holds one row per pair of users, so a request first looks
for that pair's row and decides from its state. The route layer calls this and
turns FriendRequestNotAllowed into an error response.
"""

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Friendship


class FriendRequestNotAllowed(Exception):
    """The pair's history forbids this request (declined by them, or blocked)."""


def _pair_row(session: Session, a: int, b: int) -> Friendship | None:
    return session.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == a, Friendship.addressee_id == b),
                and_(Friendship.requester_id == b, Friendship.addressee_id == a),
            )
        )
    )


def send_friend_request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
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
    session.flush()  # write the caller's pending changes first, so their errors stay theirs
    try:
        with session.begin_nested():  # a failed insert undoes only itself
            session.add(request)
    except IntegrityError:
        # Either the other user asked at the same instant (their row now exists:
        # rerun and the rules above handle it), or the request is impossible
        # (asking yourself, or a user who does not exist).
        if _pair_row(session, requester_id, addressee_id) is not None:
            return send_friend_request(session, requester_id, addressee_id)
        raise FriendRequestNotAllowed("cannot ask yourself or a user who does not exist") from None
    return request
