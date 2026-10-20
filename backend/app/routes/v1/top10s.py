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