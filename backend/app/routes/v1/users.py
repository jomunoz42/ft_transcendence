from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_session
from app.db.models import User
<<<<<<< HEAD
=======
from app.crud.user import create_user, userSignup, UserAlreadyExists
from app.crud.profile import create_profile, ErrorCreatingProfile
>>>>>>> 1604070 (checkpoint)

router = APIRouter()

@router.get("/")
def get_all(session: Session = Depends(get_session)):
	try:
		users = session.query(User).all()
	except:
		raise HTTPException(status_code=400, detail="Error when fetching users")
	return users

@router.get("/me")
def get_me(session: Session = Depends(get_session)):
	user = session.query(User).filter(User.id == 1).first()
	if not user:
		raise HTTPException(status_code=404, detail="User not found")
	return {
		"id": user.id,
		"email": user.email,
<<<<<<< HEAD
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
=======
		"password_hash": "••••••••••",
	}

@router.post("/me")
def post_me(data: userSignup, session: Session = Depends(get_session)):
	try:
		user = create_user(data, session)
	except Exception as error:
		session.rollback()
		raise HTTPException(status_code=409, detail=str(error))
	try:
		profile = create_profile(user.id, session)
	except ErrorCreatingProfile as error:
		session.rollback()
		raise HTTPException(status_code=409, detail=str(error))
	session.commit()
	return {
		"user": user,
		"profile": profile
	}
>>>>>>> 1604070 (checkpoint)
