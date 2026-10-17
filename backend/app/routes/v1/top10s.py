from fastapi import APIRouter, Depends
from app.db.models import Top10Entry, User
from sqlalchemy.orm import Session
from app.db import get_session, get_current_user
from app.crud.top10 import create_top10comment

router = APIRouter()

@router.get("")
@router.get("/")
def get_all(session: Session = Depends(get_session)):
	top10s = session.query(Top10Entry).all()
	return top10s

@router.post("/{user_id}/comment")
def post_comment(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
	comment = create_top10comment(user_id=user_id, body="Hello", session=session, current_user=current_user)
	session.commit()
	return comment
