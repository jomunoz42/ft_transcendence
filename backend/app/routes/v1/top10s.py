from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.auth.current_user import current_user
from app.db.models import User
from app.crud.top10 import Top10Add, Top10Update, create_top10, read_top10s, read_top10, update_top10, delete_top10
from app.crud.user import read_user
from app.crud.profile import read_profile
from app.crud.friendship import are_friends, is_blocked
from app import errors

router = APIRouter()

def _can_view_top10(user_id: int, current_user: User, session: Session):
	if user_id == current_user.id:
		return
	user = read_user(user_id=user_id, session=session)
	if not user:
		raise errors.HTTP_404_USER_NOT_FOUND
	if is_blocked(session, user_id, current_user.id):
		raise errors.HTTP_404_NOT_FOUND
	profile = read_profile(profile_id=user.profile.id, session=session)
	if not profile:
		raise errors.HTTP_404_PROFILE_NOT_FOUND
	if profile.is_top10_public:
		return
	if are_friends(session, current_user.id, user_id):
		return
	raise errors.HTTP_403_NOT_FRIEND

@router.get("/{user_id}/top10")
def get_top10s(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	_can_view_top10(user_id, current_user, session)
	entries = read_top10s(user_id=user_id, session=session)
	return entries

@router.get("/{user_id}/top10/{top10_id}")
def get_top10(user_id: int, top10_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	_can_view_top10(user_id, current_user, session)
	entry = read_top10(user_id=user_id, top10_id=top10_id, session=session)
	if not entry:
		raise errors.HTTP_404_NOT_FOUND
	return entry

@router.post("/{user_id}/top10")
def add_top10(user_id: int, req: Top10Add, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	if user_id != current_user.id:
		raise errors.HTTP_403_FORBIDDEN
	entry = create_top10(user_id=current_user.id, data=req, session=session)
	session.commit()
	session.refresh(entry)
	return entry

@router.post("/{user_id}/top10/{top10_id}")
def edit_top10(user_id: int, top10_id: int, req: Top10Update, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	if user_id != current_user.id:
		raise errors.HTTP_403_FORBIDDEN
	entry = update_top10(user_id=current_user.id, top10_id=top10_id, data=req, session=session)
	session.commit()
	session.refresh(entry)
	return entry

@router.delete("/{user_id}/top10/{top10_id}")
def remove_top10(user_id: int, top10_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	if user_id != current_user.id:
		raise errors.HTTP_403_FORBIDDEN
	delete_top10(user_id=current_user.id, top10_id=top10_id, session=session)
	session.commit()
	return None
