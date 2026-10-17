from fastapi import APIRouter, Depends, HTTPException, responses
from sqlalchemy.orm import Session
from app.db import get_session, get_current_user
from app.crud.profile import read_profile, read_profiles, update_profile, profileUpdate
from app.crud.user import read_user
from app.db.models import User
from app.utils import are_friends

router = APIRouter()

@router.get("/")
def get_profiles(session: Session = Depends(get_session)):
	try:
		profiles = read_profiles(session)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return profiles

@router.get("/me")
def get_me(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
	profile = read_profile(profile_id=current_user.profile.id, session=session)
	if not profile:
		raise HTTPException(status_code=404, detail="profile not found")
	profile.user # TODO: Ask why this work to see the user in the response
	return profile

@router.post("/me")
def update_me(data: profileUpdate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
	try:
		user = update_profile(profile_id=current_user.profile.id, data=data, session=session)
	except Exception as error:
		session.rollback()
		raise HTTPException(status_code=400, detail=str(error))
	session.commit()
	return user

@router.get("/{user_id}")
def get_profile(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
	is_owner = (user_id == current_user.id)
	if is_owner:
		return responses.RedirectResponse(url="me", status_code=303)
	user = read_user(user_id=user_id, session=session)
	if not user:
		raise HTTPException(status_code=404, detail="user not found")
	profile = read_profile(profile_id=user.profile.id, session=session)
	if not profile:
		raise HTTPException(status_code=404, detail="profile not found")
	is_friend = are_friends(session, current_user.id, user_id)
	result = {
		"avatar_url": profile.avatar_url,
		"display_name": profile.display_name,
		"bio": profile.bio,
	}
	if profile.is_top10_public:
		result["top10_entries"] = profile.user.top10_entries,
	if is_friend:
		result["top10_entries"] = profile.user.top10_entries,
		result["comments"] = profile.user.comments
		result["reactions"] = profile.user.reactions
	return result
