"""Friend requests: what happens when one user asks another to be friends.

The friendships table holds one row per pair of users, so a request first looks
for that pair's row and decides from its state. The route layer calls this and
turns FriendRequestNotAllowed into an error response.
"""

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import Friendship


class FriendRequestNotAllowed(Exception):
    """The pair's history forbids this request (declined by them, or blocked)."""


def send_friend_request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
    existing = session.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == requester_id, Friendship.addressee_id == addressee_id),
                and_(Friendship.requester_id == addressee_id, Friendship.addressee_id == requester_id),
            )
        )
    )
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

    # ponytail: if both users ask at the same instant, both see no row and the
    # second insert hits ux_friendships_unordered_pair (IntegrityError). No duplicate
    # row can exist; a retry finds the pending row and accepts it. Catch and retry
    # here once the endpoint exists, if it shows up in practice.
    request = Friendship(requester_id=requester_id, addressee_id=addressee_id)
    session.add(request)
    session.flush()
    return request
