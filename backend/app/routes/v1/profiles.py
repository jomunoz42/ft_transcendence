from fastapi import APIRouter, Depends, Response, status, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from app.db.models import User, Profile, Friendship
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from app.db import get_session, get_current_user
from app.utils import are_friends

router = APIRouter()

@router.get("/")
def get_all(
	response: Response,
	session: Session = Depends(get_session)
):
	profiles = session.query(Profile).all()
	return profiles

@router.get("/{user_id}")
def get_profile(
	response: Response,
	user_id: int,
	session: Session = Depends(get_session),
	current_user: User = Depends(get_current_user)
):
	profile = session.query(Profile).filter(Profile.user_id == user_id).first()
	if not profile:
		raise HTTPException(status_code=404, detail="profile not found")

	is_owner = (user_id == current_user.id)
	print(is_owner)
	if is_owner:
		return RedirectResponse(url="/users/me", status_code=303)
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
