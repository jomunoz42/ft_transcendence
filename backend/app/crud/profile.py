from sqlalchemy.orm import Session
from app.db.models import Profile, User
from pydantic import BaseModel, field_validator
from typing import Optional

class ProfileUpdate(BaseModel):
	display_name: Optional[str] = None
	bio: Optional[str] = None
	is_top10_public: Optional[bool] = None

	@field_validator("display_name")
	@classmethod
	def _display_name(cls, v: Optional[str]) -> Optional[str]:
		"""Same rule as registration: stripped, not empty, no NUL (PostgreSQL rejects NUL in text)."""
		if v is None:
			return v
		v = v.strip()
		if not v:
			raise ValueError("required")
		if "\x00" in v:
			raise ValueError("contains a NUL character")
		return v

	@field_validator("bio", "avatar_url")
	@classmethod
	def _no_nul(cls, v: Optional[str]) -> Optional[str]:
		"""PostgreSQL rejects NUL in text, which would be a 500."""
		if v is not None and "\x00" in v:
			raise ValueError("contains a NUL character")
		return v

def create_profile(user_id: int, session: Session):
	profile = Profile(user_id=user_id)
	session.add(profile)
	session.flush()
	return profile

def read_profile(profile_id: int, session: Session):
	return session.query(Profile).join(User).where(Profile.id == profile_id).first()

def read_profiles(session: Session):
	return session.query(Profile).join(User).filter(User.deleted_at.is_(None)).all()

def update_profile(profile_id: int, data: ProfileUpdate, session: Session, current_user: User):
	profile = session.query(Profile).where(Profile.id == profile_id).first()
	profileData = data.model_dump(exclude_unset=True, exclude=None)
	for k, v in profileData.items():
		setattr(profile, k, v)
		session.flush()
	return profile
