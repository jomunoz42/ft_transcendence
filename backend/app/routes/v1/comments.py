from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.auth.current_user import current_user
from app.db.models import User
from app.crud.comment import create_comment, read_comments, update_comment, delete_comment, CommentCreate, can_interact
from app.crud.notification import NotificationEvents
from app.realtime.notifications import NotificationsNotifier, get_notifications_notifier
from app import errors

router = APIRouter()

@router.get("/{user_id}/comments")
def get_comments(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	comments = read_comments(user_id=user_id, session=session, current_user=current_user)
	return comments

@router.post("/{user_id}/comments")
def add_comment(user_id: int, req: CommentCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user), notify_notifications: NotificationsNotifier = Depends(get_notifications_notifier)):
	events: NotificationEvents = []
	comment = create_comment(user_id=user_id, body=req.body, session=session, current_user=current_user, events=events)
	session.commit()
	session.refresh(comment)
	notify_notifications(events)
	return comment

@router.post("/{user_id}/comments/{comment_id}")
def edit_comment(comment_id: int, user_id: int, req: CommentCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user), notify_notifications: NotificationsNotifier = Depends(get_notifications_notifier)):
	if not can_interact(session, user_id, current_user):
		raise errors.HTTP_404_NOT_FOUND
	events: NotificationEvents = []
	comment = update_comment(user_id=user_id, comment_id=comment_id, body=req.body, session=session, current_user=current_user, events=events)
	session.commit()
	session.refresh(comment)
	notify_notifications(events)
	return comment

@router.delete("/{user_id}/comments/{comment_id}")
def remove_comment(comment_id: int, user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user), notify_notifications: NotificationsNotifier = Depends(get_notifications_notifier)):
	events: NotificationEvents = []
	delete_comment(user_id=user_id, comment_id=comment_id, session=session, current_user=current_user, events=events)
	session.commit()
	notify_notifications(events)
	return None
