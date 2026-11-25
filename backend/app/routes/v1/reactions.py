from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.auth.current_user import current_user
from app.db.models import User
from app.crud.reaction import create_reaction, read_reactions, delete_reaction, ReactionCreate
from app.crud.notification import NotificationEvents
from app.realtime.notifications import NotificationsNotifier, get_notifications_notifier

router = APIRouter()

@router.get("/{user_id}/reactions")
def get_reactions(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	reaction = read_reactions(user_id=user_id, session=session, current_user=current_user)
	return reaction

@router.post("/{user_id}/reactions")
def add_reaction(user_id: int, req: ReactionCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user), notify_notifications: NotificationsNotifier = Depends(get_notifications_notifier)):
	events: NotificationEvents = []
	reaction = create_reaction(user_id=user_id, reaction=req.reaction, session=session, current_user=current_user, events=events)
	session.commit()
	session.refresh(reaction)
	notify_notifications(events)
	return reaction

@router.delete("/{user_id}/reactions")
def remove_reaction(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user), notify_notifications: NotificationsNotifier = Depends(get_notifications_notifier)):
	events: NotificationEvents = []
	reaction = delete_reaction(user_id=user_id, session=session, current_user=current_user, events=events)
	session.commit()
	notify_notifications(events)
	return reaction
