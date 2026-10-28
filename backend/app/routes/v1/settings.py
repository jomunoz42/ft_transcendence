<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> b344a7e (final)
# TODO: remove the "" and "/"
from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from app.db import get_session
from app.auth.current_user import current_user
<<<<<<< HEAD
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
=======
from sqlalchemy.orm import Session
from app.db.models import User
from app.db import _me
from app.crud.user import update_user, delete_user, UserUpdate
>>>>>>> b344a7e (final)

router = APIRouter()

@router.get("")
@router.get("/")
<<<<<<< HEAD
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
=======
def get_me(current_user: User = Depends(current_user)):
	return _me(current_user)
>>>>>>> b344a7e (final)

@router.post("")
@router.post("/")
def update_me(data: UserUpdate, current_user: User = Depends(current_user), session: Session = Depends(get_session)):
	try:
		user = update_user(user_id=current_user.id, data=data, session=session)
	except Exception as error:
<<<<<<< HEAD
		HTTPException(status_code=400, detail=str(error))
>>>>>>> 1604070 (checkpoint)
=======
		session.rollback()
		raise HTTPException(status_code=400, detail=str(error))
>>>>>>> b344a7e (final)
	session.commit()
	return user

@router.delete("")
@router.delete("/")
<<<<<<< HEAD
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
=======
def delete_me(response: Response, session: Session = Depends(get_session), current_user: User = Depends(current_user), token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
>>>>>>> b344a7e (final)
	try:
		delete_user(user_id=current_user.id, session=session)
	except Exception as error:
		session.rollback()
		raise HTTPException(status_code=400, detail=str(error))
	if token:
		end_session(session, token)
	session.commit()
<<<<<<< HEAD
	return {
		"profile": profile,
		"user": user
	}
>>>>>>> 1604070 (checkpoint)
=======
	response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, secure=True, samesite="lax")
>>>>>>> b344a7e (final)
