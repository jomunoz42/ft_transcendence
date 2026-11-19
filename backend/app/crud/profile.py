from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.models import Profile, User, Top10Entry, Song
from pydantic import BaseModel
from typing import Optional

class ProfileUpdate(BaseModel):
	display_name: Optional[str] = None
	avatar_url: Optional[str] = None
	bio: Optional[str] = None
	is_top10_public: Optional[bool] = None

def create_profile(user_id: int, session: Session):
	profile = Profile(user_id=user_id)
	session.add(profile)
	session.flush()
	return profile

def read_profile(profile_id: int, session: Session):
	return session.query(Profile).join(User).where(Profile.id == profile_id).first()

def read_profiles(session: Session):
	return session.query(Profile).join(User).filter(User.deleted_at.is_(None)).all()

# TODO: limit the # of top 10 to 10 max songs
# TODO: revamp this shit
def update_profile(profile_id: int, data: ProfileUpdate, session: Session, current_user: User):
	profile = session.query(Profile).where(Profile.id == profile_id).first()
	profileData = data.model_dump(exclude_unset=True, exclude=None)
	for k, v in profileData.items():
		setattr(profile, k, v)
		session.flush()
	return profile
