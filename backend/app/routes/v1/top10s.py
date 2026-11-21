from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.auth.current_user import current_user
from app.db.models import User
from app.crud.top10 import Top10Add, Top10Update, create_top10, read_top10s, read_top10, update_top10, delete_top10
from app import errors

router = APIRouter()

@router.get("/{user_id}/top10")
def get_top10s(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	entries = read_top10s(user_id=user_id, session=session)
	return entries

@router.get("/{user_id}/top10/{top10_id}")
def get_top10(user_id: int, top10_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	entry = read_top10(user_id=user_id, top10_id=top10_id, session=session)
	if not entry:
		raise errors.HTTP_404_NOT_FOUND
	return entry

@router.post("/{user_id}/top10")
def add_top10(user_id: int, req: Top10Add, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	if user_id != current_user.id:
		raise errors.HTTP_422_UNPROCESSABLE_CONTENT
	entry = create_top10(user_id=current_user.id, data=req, session=session)
	session.commit()
	return entry

@router.post("/{user_id}/top10/{top10_id}")
def edit_top10(user_id: int, top10_id: int, req: Top10Update, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	if user_id != current_user.id:
		raise errors.HTTP_422_UNPROCESSABLE_CONTENT
	entry = update_top10(user_id=current_user.id, top10_id=top10_id, data=req, session=session)
	session.commit()
	return entry

@router.delete("/{user_id}/top10/{top10_id}")
def remove_top10(user_id: int, top10_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	if user_id != current_user.id:
		raise errors.HTTP_422_UNPROCESSABLE_CONTENT
	delete_top10(user_id=current_user.id, top10_id=top10_id, session=session)
	session.commit()
	return None
