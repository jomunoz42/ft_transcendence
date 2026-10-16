from fastapi import APIRouter, Depends, HTTPException
from app.db import get_current_user, get_session
from sqlalchemy.orm import Session
from app.db.models import User
from app.crud.user import update_user, delete_user, userUpdate
from app.crud.profile import delete_profile

router = APIRouter()

@router.get("")
@router.get("/")
def get_me(current_user: User = Depends(get_current_user)):
	return current_user

@router.post("")
@router.post("/")
def update_me(data: userUpdate, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
	try:
		print(current_user)
		user = update_user(user_id=current_user.id, data=data, session=session)
	except Exception as error:
		HTTPException(status_code=400, detail=str(error))
	session.commit()
	return user

@router.delete("")
@router.delete("/")
def delete_me(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
	try:
		profile = delete_profile(profile_id=current_user.profile.id, session=session)
		user = delete_user(user_id=current_user.id, session=session)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	session.commit()
	return {
		"profile": profile,
		"user": user
	}
