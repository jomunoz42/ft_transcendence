from fastapi import APIRouter, Depends, Response, status, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.db.models import User
from app.crud.user import create_user, userSignup, UserAlreadyExists

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
def post_me(response: Response, data: userSignup, session: Session = Depends(get_session)):
	try:
		create_user(session)
	except UserAlreadyExists as error:
		HTTPException(status_code=409, detail=str(error))
	except Exception as error:
		HTTPException(status_code=409, detail=str(error))
	return {"username": data.username}

@router.patch("/me")
def patch_me(data: UserCreate):
	return {"username": data.username}
