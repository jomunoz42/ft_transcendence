from app.db.models import Top10Comment, Profile, User
from app.crud.friendship import are_friends, is_blocked
from app import errors
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.crud.notification import NotificationEvents
from app.notifications import advance_updated_at, record_action


def _can_interact(session: Session, owner_id: int, current_user: User) -> bool:
    """True if current_user is the owner, friends with owner, or the owner's top10 is public — and not blocked."""
    if owner_id == current_user.id:
        return True
    if is_blocked(session, owner_id, current_user.id):
        return False
    if are_friends(session=session, a=owner_id, b=current_user.id):
        return True
    profile = session.query(Profile).filter(Profile.user_id == owner_id).first()
    return profile is not None and profile.is_top10_public

class CommentCreate(BaseModel):
	body: str

def create_comment(user_id: int, body: str, session: Session, current_user: User, events: NotificationEvents | None = None):
	top10comment = Top10Comment(top10_owner_id=user_id, author_id=current_user.id, body=body)
	session.add(top10comment)
	session.flush()
	record_action(session, top10comment, "comment.created", user_id, current_user.id, events)
	return top10comment

def read_comments(user_id: int, session: Session, current_user: User):
	if not _can_interact(session, user_id, current_user):
		raise errors.HTTP_403_NOT_FRIEND
	return session.query(Top10Comment).where(
		Top10Comment.top10_owner_id == user_id
	).order_by(Top10Comment.updated_at.desc()).all()

def read_comment(comment_id: int, user_id: int, session: Session, current_user: User):
	return session.query(Top10Comment).where(
		and_(
			Top10Comment.id == comment_id,
			Top10Comment.top10_owner_id == user_id,
		)
	).first()

def update_comment(comment_id: int, user_id: int, body: str, session: Session, current_user: User, events: NotificationEvents | None = None):
	top10comment = session.query(Top10Comment).where(
		and_(
			Top10Comment.id == comment_id,
			Top10Comment.author_id == current_user.id,
			Top10Comment.top10_owner_id == user_id,
		)
	).populate_existing().with_for_update().first()
	if not top10comment:
		raise errors.HTTP_404_NOT_FOUND
	if top10comment.body == body:
		return top10comment
	top10comment.body = body
	advance_updated_at(top10comment)
	session.flush()
	record_action(session, top10comment, "comment.updated", user_id, current_user.id, events)
	return top10comment

def delete_comment(comment_id: int, user_id: int, session: Session, current_user: User, events: NotificationEvents | None = None):
	top10comment = session.query(Top10Comment).where(
		and_(
			Top10Comment.id == comment_id,
			Top10Comment.top10_owner_id == user_id,
		)
	).populate_existing().with_for_update().first()
	if not top10comment:
		raise errors.HTTP_404_NOT_FOUND
	# Author can always delete their own comment; top10 owner can delete any comment on their page
	if top10comment.author_id != current_user.id and user_id != current_user.id:
		raise errors.HTTP_404_NOT_FOUND
	session.delete(top10comment)
	session.flush()
	record_action(session, top10comment, "comment.deleted", user_id, current_user.id, events)
	return None
