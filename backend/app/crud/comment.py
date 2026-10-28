from app.db.models import Top10Comment, User
from app.db.friendships import are_friends
from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_

class CommentCreate(BaseModel):
	body: str

def create_comment(user_id: int, body: str, session: Session, current_user: User):
	if not are_friends(session=session, a=user_id, b=current_user.id):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not friend")
	try:
		top10comment = Top10Comment(top10_owner_id=user_id, author_id=current_user.id, body=body)
		session.add(top10comment)
		session.flush()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when creating comment")
	return top10comment

def read_comment(comment_id: int, user_id: int, session: Session, current_user: User):
	if not are_friends(session=session, a=user_id, b=current_user.id):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not friend")
	try:
		top10comment = session.query(Top10Comment).where(
			and_(
				Top10Comment.id == comment_id,
				Top10Comment.top10_owner_id == user_id,
			)
		).first()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when reading comment")
	return top10comment

def read_comments(user_id: int, session: Session, current_user: User):
	if not are_friends(session=session, a=user_id, b=current_user.id):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not friend")
	try:
		top10comments = session.query(Top10Comment).where(
			Top10Comment.top10_owner_id == user_id
		).order_by(Top10Comment.updated_at.desc()).all()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when reading comments")
	return top10comments

def update_comment(comment_id: int, user_id: int, body: str, session: Session, current_user: User):
	try:
		top10comment = session.query(Top10Comment).where(
			and_(
				Top10Comment.id == comment_id,
				Top10Comment.author_id == current_user.id,
				Top10Comment.top10_owner_id == user_id,
			)
		).first()
		top10comment.body = body
		session.flush()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when updating comment")
	return top10comment

def delete_comment(comment_id: int, user_id: int, session: Session, current_user: User):
	try:
		top10comment = session.query(Top10Comment).where(
			and_(
				Top10Comment.id == comment_id,
				Top10Comment.author_id == current_user.id,
				Top10Comment.top10_owner_id == user_id,
			)
		).first()
		session.delete(top10comment)
		session.flush()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when deleting comment")
	return None
