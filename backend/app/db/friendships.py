"""Friend requests: what happens when one user asks another to be friends.

The friendships table holds one row per pair of users, so a request first looks
for that pair's row and decides from its state. The route layer calls this and
turns FriendRequestNotAllowed into an error response.
"""

from sqlalchemy.orm import Session

from app.crud.friendship import ErrorCreatingFriendship, create_friendship, read_friendship
from app.db.models import Friendship


class FriendRequestNotAllowed(Exception):
    """The pair's history forbids this request (declined by them, or blocked)."""


def send_friend_request(session: Session, requester_id: int, addressee_id: int) -> Friendship:
    """Ask another user to be friends; the pair's history decides the result. Never commits."""
    existing = read_friendship(session, requester_id, addressee_id)
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

    try:
        request = create_friendship(session, requester_id, addressee_id)
    except ErrorCreatingFriendship:
        raise FriendRequestNotAllowed("cannot ask yourself or a user who does not exist") from None
    if request is None:
        return send_friend_request(session, requester_id, addressee_id)
    return request
