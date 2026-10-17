from app.db import get_current_user
from app.db.models import Top10Entry, Top10Comment, Top10Reaction, User
from fastapi import Depends
from sqlalchemy.orm import Session

def create_top10comment(user_id: int, body: str, session: Session, current_user: User):
	top10comment = Top10Comment(top10_owner_id=user_id, author_id=current_user.id, body=body)
	session.add(top10comment)
	session.flush()
	return top10comment

def update_top10comment(body: str, current_user: User = Depends(get_current_user), session = Session):
	pass

def delete_top10comment(current_user: User = Depends(get_current_user), session = Session):
	pass


def create_top10reaction(user_id: int, current_user: User = Depends(get_current_user), session = Session):
	pass

def update_top10reaction(current_user: User = Depends(get_current_user), session = Session):
	pass

def delete_top10reaction(current_user: User = Depends(get_current_user), session = Session):
	pass
