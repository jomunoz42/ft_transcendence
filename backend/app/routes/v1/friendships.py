from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from app.db.models import Friendship
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.db import get_session, get_current_user

router = APIRouter()

@router.get("/")
def get_all(
	response: Response,
	session: Session = Depends(get_session)
):
	friendships = session.query(Friendship).all()
	return friendships
