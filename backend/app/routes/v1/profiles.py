# TODO: Add rolllback on comments failure

from fastapi import APIRouter, Depends, responses
from sqlalchemy.orm import Session
from app.db import get_session
from app.auth.current_user import current_user
from app.crud.profile import read_profile, read_profiles, update_profile, ProfileUpdate
from app.crud.user import read_user
from app.db import _me_profile
from app.db.models import User
from app.crud.friendship import are_friends
from app import errors

router = APIRouter()

@router.get("")
def get_profiles(session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	profiles = read_profiles(session)
	return profiles

@router.get("/me")
def get_me(session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	profile = read_profile(profile_id=current_user.profile.id, session=session)
	user = read_user(user_id=current_user.id, session=session)
	if not profile:
		raise errors.HTTP_404_PROFILE_NOT_FOUND
	return _me_profile(profile) |\
		{"top10_entries": user.top10_entries, "comments": user.comments, "reactions": user.reactions}

@router.post("/me")
def edit_me(data: ProfileUpdate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	profile = update_profile(profile_id=current_user.profile.id, data=data, session=session, current_user=current_user)
	session.commit()
	return _me_profile(profile)

@router.get("/{user_id}")
def get_profile(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	is_owner = (user_id == current_user.id)
	if is_owner:
		return responses.RedirectResponse(url="me", status_code=303)
	user = read_user(user_id=user_id, session=session)
	if not user:
		raise errors.HTTP_404_USER_NOT_FOUND
	profile = read_profile(profile_id=user.profile.id, session=session)
	if not profile:
		raise errors.HTTP_404_PROFILE_NOT_FOUND
	is_friend = are_friends(session, current_user.id, user_id)
	result = {
		"avatar_url": profile.avatar_url,
		"display_name": profile.display_name,
		"bio": profile.bio,
	}
	if profile.is_top10_public or is_friend:
		result["top10_entries"] = profile.user.top10_entries
	if is_friend:
		result["comments"] = profile.user.comments
		result["reactions"] = profile.user.reactions
	return result
