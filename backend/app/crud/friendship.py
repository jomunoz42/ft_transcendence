"""Friendship and block queries: read and write rows, never decide what is allowed.

Only queries with logic of their own live here. Plain `session.add`,
`session.delete` and status changes stay inline in the route's rule functions.
Nothing here commits.
"""

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.db.models import Friendship, User, Block
from app import errors

def read_friendship(session: Session, a: int, b: int) -> Friendship | None:
    """The friendships row for this pair of users, whichever of the two asked."""
    return session.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == a, Friendship.addressee_id == b),
                and_(Friendship.requester_id == b, Friendship.addressee_id == a),
            )
        )
    )


def create_friendship(session: Session, requester_id: int, addressee_id: int) -> Friendship | None:
    """Insert a pending request; None if the pair's row appeared meanwhile, ErrorCreatingFriendship on a database rule."""
    request = Friendship(requester_id=requester_id, addressee_id=addressee_id)
    session.flush()  # keep: the caller's pending errors must not be blamed on this insert
    try:
        with session.begin_nested():
            session.add(request)
    except IntegrityError:
        if read_friendship(session, requester_id, addressee_id) is not None:
            return None
        raise errors.HTTP_404_NOT_FOUND from None
    return request


def are_friends(session: Session, a: int, b: int) -> bool:
    """True only when the pair's row is accepted; the order of a and b does not matter."""
    row = read_friendship(session, a, b)
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

def is_blocked(session: Session, a: int, b: int) -> bool:
    """True when either user has blocked the other."""
    block = session.scalar(
        select(Block).where(
            or_(
                and_(Block.blocker_id == a, Block.blocked_id == b),
                and_(Block.blocker_id == b, Block.blocked_id == a),
            )
        )
    )
    return block is not None

def list_pending(session: Session, user_id: int) -> tuple[list[User], list[User]]:
    """Pending requests as (users who asked me, users I asked), deleted accounts left out, each ordered by id."""
    other = aliased(User)

    incoming = list(session.scalars(
        select(other)
        .join(Friendship, and_(Friendship.addressee_id == user_id, Friendship.requester_id == other.id))
        .where(Friendship.status == "pending", other.deleted_at.is_(None))
        .order_by(other.id)
    ))

    outgoing = list(session.scalars(
        select(other)
        .join(Friendship, and_(Friendship.requester_id == user_id, Friendship.addressee_id == other.id))
        .where(Friendship.status == "pending", other.deleted_at.is_(None))
        .order_by(other.id)
    ))
    return incoming, outgoing
