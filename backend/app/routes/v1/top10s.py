from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from app.db.models import Top10Entry, User
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.db import get_session, get_current_user

router = APIRouter()

@router.get("/")
def get_all(
	response: Response,
	session: Session = Depends(get_session)
):
	top10s = session.query(Top10Entry).all()
	return top10s

@router.get("/{user_id}")
def get_user(
	response: Response,
	user_id: int,
	session: Session = Depends(get_session)
):
	user = session.query(User).filter(User.id == user_id).first()
	return user.top10_entries
