# TODO: standardize all files
# TODO: Force types in all functions
from app.db.models import User, Top10Reaction
from app.db.friendships import are_friends
from fastapi import HTTPException, status
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.orm import Session
from sqlalchemy import and_

class ReactionCreate(BaseModel):
	reaction: Literal["like", "dislike"]

def create_reaction(user_id: int, reaction: Literal["like", "dislike"], session: Session, current_user: User):
	if not are_friends(session=session, a=user_id, b=current_user.id):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not friend")
	try:
		top10reaction = session.query(Top10Reaction).where(
			and_(
				Top10Reaction.author_id == current_user.id,
				Top10Reaction.top10_owner_id == user_id,
			)
		).first()
		if top10reaction is not None:
			top10reaction.reaction = reaction
		else:
			top10reaction = Top10Reaction(top10_owner_id=user_id, author_id=current_user.id, reaction=reaction)
			session.add(top10reaction)
		session.flush()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when creating reaction")
	return top10reaction

def read_reactions(user_id: int, session: Session, current_user: User):
	if not are_friends(session=session, a=user_id, b=current_user.id):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not friend")
	try:
		top10reactions = session.query(Top10Reaction).where(
			Top10Reaction.top10_owner_id == user_id
		).order_by(Top10Reaction.updated_at.desc()).all()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when reading reaction")
	return top10reactions

def delete_reaction(user_id: int, session: Session, current_user: User):
	try:
		top10reaction = session.query(Top10Reaction).where(
			and_(
				Top10Reaction.author_id == current_user.id,
				Top10Reaction.top10_owner_id == user_id,
			)
		).first()
		session.delete(top10reaction)
		session.flush()
	except:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="error when deleting reaction")
	return None
