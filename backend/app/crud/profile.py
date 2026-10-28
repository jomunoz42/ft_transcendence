from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.models import Profile, User, Top10Entry, Song
from pydantic import BaseModel
from typing import Optional, Literal

class SongAdd(BaseModel):
	provider: str = "manual"
	provider_id: str = "manual"
	title: str
	artist: str
	rank: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

class ProfileUpdate(BaseModel):
	display_name: Optional[str] = None
	avatar_url: Optional[str] = None
	bio: Optional[str] = None
	is_top10_public: Optional[bool] = None
	top10: Optional[list[SongAdd]] = None

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
		profile = session.query(Profile).join(User).where(Profile.id == profile_id).first()
	except:
		raise ErrorReadingProfile("Error when reading profile")
	return profile

def read_profiles(session: Session):
	try:
		profiles = session.query(Profile).join(User).filter(User.deleted_at.is_(None)).all()
	except Exception as e:
		raise ErrorReadingProfiles("Error when reading profiles: " + str(e))
	return profiles

# TODO: limit the # of top 10 to 10 max songs
# TODO: revamp this shit
def update_profile(profile_id: int, data: ProfileUpdate, session: Session, current_user: User):
	profile = session.query(Profile).where(Profile.id == profile_id).first()
	try:
		profileData = data.model_dump(exclude_unset=True, exclude=None)
		for k, v in profileData.items():
			if k == "top10":
				top10entries = []
				for i in v:
					song = session.query(Song).where(
						and_(
							Song.title == i.get("title"),
							Song.artist == i.get("artist"),
						)
					).first()
					if song is None:
						song = Song(
							provider="manual",
							provider_id="manual", # TODO: Add the logic, ID must be unique
							title=i.get("title"),
							artist=i.get("artist"),
						)
						session.add(song)
						session.flush()
					top10entries.append(Top10Entry(
						user_id=current_user.id,
						song_id=song.id,
						rank=i.get("rank"),
					))
				current_user.top10_entries = top10entries
				session.flush()
			else:
				setattr(profile, k, v)
				session.flush()
	except:
		raise ErrorUpdatingProfile("Error when updating profile")
	return profile

# TODO: Check if profile should be deleted as well
# def delete_profile(profile_id: int, session: Session):
# 	try:
# 		profile = session.query(Profile).where(Profile.id == profile_id).delete()
# 		session.flush()
# 	except:
# 		raise ErrorDeletingProfile("Error when deleting profile")
# 	return None
