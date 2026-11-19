from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.auth.current_user import current_user
from app.db.models import User
from app.crud.friendship import are_friends
from app.crud.comment import create_comment, read_comments, update_comment, delete_comment, CommentCreate
from app import errors

router = APIRouter()

@router.get("/{user_id}/comments")
def get_comments(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	comments = read_comments(user_id=user_id, session=session, current_user=current_user)
	return comments

@router.post("/{user_id}/comments")
def add_comment(user_id: int, req: CommentCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	is_friend = are_friends(session=session, a=user_id, b=current_user.id)
	# TODO: Add a possibility for non-friend but public top 10 to be commented, unless blocked
	if not is_friend:
		raise errors.HTTP_422_MUST_BE_FRIEND_TO_COMMENT
	comment = create_comment(user_id=user_id, body=req.body, session=session, current_user=current_user)
	session.commit()
	return comment

@router.post("/{user_id}/comments/{comment_id}")
def edit_comment(comment_id: int, user_id: int, req: CommentCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	comment = update_comment(user_id=user_id, comment_id=comment_id, body=req.body, session=session, current_user=current_user)
	session.commit()
	return comment

@router.delete("/{user_id}/comments/{comment_id}")
def remove_comment(comment_id: int, user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	delete_comment(user_id=user_id, comment_id=comment_id, session=session, current_user=current_user)
	session.commit()
	return None
