from app.db.models import Top10Comment, User
from app.crud.friendship import are_friends
from app import errors
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.crud.notification import NotificationEvents
from app.notifications import advance_updated_at, record_action

class CommentCreate(BaseModel):
	body: str

def create_comment(user_id: int, body: str, session: Session, current_user: User, events: NotificationEvents | None = None):
	top10comment = Top10Comment(top10_owner_id=user_id, author_id=current_user.id, body=body)
	session.add(top10comment)
	session.flush()
	record_action(session, top10comment, "comment.created", user_id, current_user.id, events)
	return top10comment

def read_comment(comment_id: int, user_id: int, session: Session, current_user: User):
	return session.query(Top10Comment).where(
		and_(
			Top10Comment.id == comment_id,
			Top10Comment.top10_owner_id == user_id,
		)
	).first()

def read_comments(user_id: int, session: Session, current_user: User):
	if not are_friends(session=session, a=user_id, b=current_user.id):
		raise errors.HTTP_403_NOT_FRIEND
	return session.query(Top10Comment).where(
		Top10Comment.top10_owner_id == user_id
	).order_by(Top10Comment.updated_at.desc()).all()

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
			Top10Comment.author_id == current_user.id,
			Top10Comment.top10_owner_id == user_id,
		)
	).populate_existing().with_for_update().first()
	if not top10comment:
		raise errors.HTTP_404_NOT_FOUND
	session.delete(top10comment)
	session.flush()
	record_action(session, top10comment, "comment.deleted", user_id, current_user.id, events)
	return None
