from sqlalchemy.orm import Session
from app.db.models import Profile, Top10Entry
from pydantic import BaseModel
from typing import Optional

class top10EntryAdd(BaseModel):
	provider: str
	provider_id: str
	title: str
	artist: str

class profileUpdate(BaseModel):
	display_name: Optional[str] = None
	avatar_url: Optional[str] = None
	bio: Optional[str] = None
	is_top10_public: Optional[str] = None
	top10: Optional[list[top10EntryAdd]] = None

class ErrorCreatingProfile(Exception):
    pass
class ErrorReadingProfile(Exception):
    pass
class ErrorReadingProfiles(Exception):
    pass
class ErrorUpdatingProfile(Exception):
    pass
class ErrorDeletingProfile(Exception):
    pass

def create_profile(user_id: int, session: Session):
	try:
		profile = Profile(user_id=user_id)
		session.add(profile)
		session.flush()
	except:
		raise ErrorCreatingProfile("Error when creating profile")
	return profile

def read_profile(profile_id: int, session: Session):
	try:
		profile = session.query(Profile).where(Profile.id == profile_id).first()
	except:
		raise ErrorReadingProfile("Error when reading profile")
	return profile

def read_profiles(session: Session):
	try:
		profiles = session.query(Profile).all()
	except:
		raise ErrorReadingProfiles("Error when reading profiles")
	return profiles

def update_profile(profile_id: int, data: profileUpdate, session: Session):
	profile = session.query(Profile).where(Profile.id == profile_id).first()
	try:
		profileData = data.model_dump(exclude_unset=True, exclude=None)
		for k, v in profileData.items():
			if k == "top10":
				pass # TODO: add the logic for adding the entries
			else:
				setattr(profile, k, v)
		session.flush()
	except:
		raise ErrorUpdatingProfile("Error when updating profile")
	return profile

def delete_profile(profile_id: int, session: Session):
	try:
		profile = session.query(Profile).where(Profile.id == profile_id).delete()
		session.flush()
	except:
		raise ErrorDeletingProfile("Error when deleting profile")
	return profile
