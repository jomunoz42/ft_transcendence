from fastapi import APIRouter, Depends
from app.db.models import User
from sqlalchemy.orm import Session
from app.db import get_session

router = APIRouter()

@router.get("/")
def get_me(session: Session = Depends(get_session)):
	users = session.query(User).all()
	return users

################################################
# me
################################################

@router.get("/me")
def get_me(session: Session = Depends(get_session)):
	user = session.query(User).filter(User.id == 1).first()
	if not user:
		return {"error": "not found"}
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

################################################
# users
################################################

@router.get("/{id}")
def get_user(id:str):
	print(id)
	return {"username": users.to_dict()}
