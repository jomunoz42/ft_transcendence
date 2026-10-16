<<<<<<< HEAD
# TODO: Fix the /me profiles
# TODO: Add rolllback on comments failure

from fastapi import APIRouter, Depends, HTTPException, responses
from sqlalchemy.orm import Session
from app.db import get_session
from app.auth.current_user import current_user
from app.crud.profile import read_profile, read_profiles, update_profile, ProfileUpdate
from app.crud.user import read_user
from app.db import _me_profile
from app.db.models import User
from app.db.friendships import are_friends
from app.crud.comment import create_comment, read_comments, update_comment, delete_comment, CommentCreate
from app.crud.reaction import create_reaction, read_reactions, delete_reaction, ReactionCreate
=======
from fastapi import APIRouter, Depends, HTTPException, responses
from sqlalchemy.orm import Session
from app.db import get_session, get_current_user
from app.crud.profile import read_profile, read_profiles, update_profile, profileUpdate
from app.crud.user import read_user
from app.db.models import User
from app.utils import are_friends
>>>>>>> 1604070 (checkpoint)

router = APIRouter()

################################################
# /profiles
################################################

@router.get("")
@router.get("/")
<<<<<<< HEAD
def get_profiles(session: Session = Depends(get_session), current_user: User = Depends(current_user)):
=======
def get_profiles(session: Session = Depends(get_session)):
>>>>>>> 1604070 (checkpoint)
	try:
		profiles = read_profiles(session)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return profiles

<<<<<<< HEAD
################################################
# /me
################################################

@router.get("/me")
def get_me(session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	profile = read_profile(profile_id=current_user.profile.id, session=session)
	user = read_user(user_id=current_user.id, session=session)
	if not profile:
		raise HTTPException(status_code=404, detail="profile not found")
	return _me_profile(profile) |\
		{"top10_entries": user.top10_entries, "comments": user.comments, "reactions": user.reactions}

@router.post("/me")
def update_me(data: ProfileUpdate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		user = update_profile(profile_id=current_user.profile.id, data=data, session=session, current_user=current_user)
=======
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
>>>>>>> 1604070 (checkpoint)
	except Exception as error:
		session.rollback()
		raise HTTPException(status_code=400, detail=str(error))
	session.commit()
	return user

<<<<<<< HEAD
################################################
# /{user_id}
################################################

@router.get("/{user_id}")
def get_profile(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
=======
@router.get("/{user_id}")
def get_profile(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
>>>>>>> 1604070 (checkpoint)
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
	if profile.is_top10_public or is_friend:
		result["top10_entries"] = profile.user.top10_entries
	if is_friend:
		result["comments"] = profile.user.comments
		result["reactions"] = profile.user.reactions
	return result

################################################
# /{user_id}/comments
################################################

@router.get("/{user_id}/comments")
def get_comments(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		comments = read_comments(user_id=user_id, session=session, current_user=current_user)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return comments

@router.post("/{user_id}/comments")
def post_comment(user_id: int, req: CommentCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		comment = create_comment(user_id=user_id, body=req.body, session=session, current_user=current_user)
		session.commit()
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return comment

def get_last_comment_id(user_id: int, session: Session, current_user: User) -> int | None:
	comments = read_comments(user_id=user_id, session=session, current_user=current_user)
	if len(comments) > 0:
		return comments[0].id

@router.post("/{user_id}/comments/latest")
def _update_last_comment(user_id: int, req: CommentCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		comment_id = get_last_comment_id(user_id=user_id, session=session, current_user=current_user)
		comment = update_comment(user_id=user_id, comment_id=comment_id, body=req.body, session=session, current_user=current_user)
		session.commit()
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return comment

@router.post("/{user_id}/comments/{comment_id}")
def _update_comment(comment_id: int, user_id: int, req: CommentCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		comment = update_comment(user_id=user_id, comment_id=comment_id, body=req.body, session=session, current_user=current_user)
		session.commit()
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return comment

@router.delete("/{user_id}/comments/{comment_id}")
def _delete_comment(comment_id: int, user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		delete_comment(user_id=user_id, comment_id=comment_id, session=session, current_user=current_user)
		session.commit()
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return None

################################################
# /{user_id}/reactions
################################################

@router.get("/{user_id}/reactions")
def get_reactions(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		reaction = read_reactions(user_id=user_id, session=session, current_user=current_user)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return reaction

@router.post("/{user_id}/reactions")
def post_reaction(user_id: int, req: ReactionCreate, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		reaction = create_reaction(user_id=user_id, reaction=req.reaction, session=session, current_user=current_user)
		session.commit()
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return reaction

@router.delete("/{user_id}/reactions")
def _delete_reaction(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(current_user)):
	try:
		reaction = delete_reaction(user_id=user_id, session=session, current_user=current_user)
		session.commit()
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return reaction
