from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.db.models import User

router = APIRouter()

@router.get("/")
def get_all(response: Response, session: Session = Depends(get_session)):
	users = session.query(User).all()
	return users

@router.get("/me")
def get_me(response: Response, session: Session = Depends(get_session)):
	user = session.query(User).filter(User.id == 1).first()
	if not user:
		response.status_code = status.HTTP_404_NOT_FOUND
		return {"status": "error", "msg": "user not found"}
	return {
		"id": user.id,
		"email": user.email,
		"password_hash": user.password_hash,
		"created_at": user.created_at,
		"updated_at": user.updated_at,
		}

@router.post("/me")
def post_me(data: UserCreate):
	return {"username": data.username}

@router.patch("/me")
def patch_me(data: UserCreate):
	return {"username": data.username}
