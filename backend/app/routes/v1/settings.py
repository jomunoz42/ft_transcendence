<<<<<<< HEAD
# TODO: remove the "" and "/"
from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from app.db import get_session
from app.auth.current_user import current_user
from sqlalchemy.orm import Session
from app.db.models import User
from app.db import _me
from app.crud.user import update_user, delete_user, UserUpdate
=======
from fastapi import APIRouter, Depends, HTTPException
from app.db import get_current_user, get_session
from sqlalchemy.orm import Session
from app.db.models import User
from app.crud.user import update_user, delete_user, userUpdate
from app.crud.profile import delete_profile
>>>>>>> 1604070 (checkpoint)

router = APIRouter()

@router.get("")
@router.get("/")
<<<<<<< HEAD
def get_me(current_user: User = Depends(current_user)):
	return _me(current_user)

@router.post("")
@router.post("/")
def update_me(data: UserUpdate, current_user: User = Depends(current_user), session: Session = Depends(get_session)):
	try:
		user = update_user(user_id=current_user.id, data=data, session=session)
	except Exception as error:
		session.rollback()
		raise HTTPException(status_code=400, detail=str(error))
=======
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
>>>>>>> 1604070 (checkpoint)
	session.commit()
	return user

@router.delete("")
@router.delete("/")
<<<<<<< HEAD
def delete_me(response: Response, session: Session = Depends(get_session), current_user: User = Depends(current_user), token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
	try:
		delete_user(user_id=current_user.id, session=session)
	except Exception as error:
		session.rollback()
		raise HTTPException(status_code=400, detail=str(error))
	if token:
		end_session(session, token)
	session.commit()
	response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, secure=True, samesite="lax")
=======
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
>>>>>>> 1604070 (checkpoint)
