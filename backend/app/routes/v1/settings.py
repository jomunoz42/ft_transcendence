# TODO: remove the "" and "/"
from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from app.db import get_session, _me
from app.auth.current_user import current_user
from sqlalchemy.orm import Session
from app.db.models import User
from app.crud.user import update_user, delete_user, UserUpdate

router = APIRouter()

@router.get("")
@router.get("/")
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

@router.post("")
@router.post("/")
def update_me(data: UserUpdate, current_user: User = Depends(current_user), session: Session = Depends(get_session)):
	try:
		user = update_user(user_id=current_user.id, data=data, session=session)
	except Exception as error:
		HTTPException(status_code=400, detail=str(error))
		session.rollback()
	session.commit()
	return user

@router.delete("")
@router.delete("/")
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
