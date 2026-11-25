from app.db.models import User, Top10Reaction
from app.crud.comment import _can_interact
from app import errors
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from app.crud.notification import NotificationEvents
from app.notifications import advance_updated_at, record_action

class ReactionCreate(BaseModel):
	reaction: Literal["like", "dislike"]

def create_reaction(user_id: int, reaction: Literal["like", "dislike"], session: Session, current_user: User, events: NotificationEvents | None = None):
	if not _can_interact(session, user_id, current_user):
		raise errors.HTTP_403_NOT_FRIEND
	top10reaction = session.query(Top10Reaction).where(
		and_(
			Top10Reaction.author_id == current_user.id,
			Top10Reaction.top10_owner_id == user_id,
		)
	).populate_existing().with_for_update().first()
	if top10reaction is not None:
		if top10reaction.reaction == reaction:
			return top10reaction
		top10reaction.reaction = reaction
		advance_updated_at(top10reaction)
		event_type = "reaction.updated"
	else:
		top10reaction = Top10Reaction(top10_owner_id=user_id, author_id=current_user.id, reaction=reaction)
		# A concurrent retry may create the same (owner, author) row after our
		# lookup. Keep the outer action transaction usable and re-read that row.
		session.flush()
		try:
			with session.begin_nested():
				session.add(top10reaction)
		except IntegrityError:
			if session.query(Top10Reaction.id).filter_by(top10_owner_id=user_id, author_id=current_user.id).first() is None:
				raise
			return create_reaction(user_id, reaction, session, current_user, events)
		event_type = "reaction.created"
	session.flush()
	record_action(session, top10reaction, event_type, user_id, current_user.id, events)
	return top10reaction

def read_reactions(user_id: int, session: Session, current_user: User):
	if not _can_interact(session, user_id, current_user):
		raise errors.HTTP_403_NOT_FRIEND
	return session.query(Top10Reaction).where(
		Top10Reaction.top10_owner_id == user_id
	).order_by(Top10Reaction.updated_at.desc()).all()

def delete_reaction(user_id: int, session: Session, current_user: User, events: NotificationEvents | None = None):
	top10reaction = session.query(Top10Reaction).where(
		and_(
			Top10Reaction.author_id == current_user.id,
			Top10Reaction.top10_owner_id == user_id,
		)
	).populate_existing().with_for_update().first()
	if not top10reaction:
		raise errors.HTTP_404_NOT_FOUND
	session.delete(top10reaction)
	session.flush()
	record_action(session, top10reaction, "reaction.deleted", user_id, current_user.id, events)
	return None
