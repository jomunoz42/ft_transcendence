from app.db.models import User, Profile
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.auth.passwords import hash_password

class userSignup(BaseModel):
	email: str
	password: str

class userUpdate(BaseModel):
	email: Optional[str] = None
	password: Optional[str] = None

class UserAlreadyExists(Exception):
    pass
class UserNotFound(Exception):
    pass
class ErrorReadingUser(Exception):
    pass
class ErrorUpdatingUser(Exception):
    pass
class ErrorDeletingUser(Exception):
    pass

def create_user(session: Session, data: userSignup):
	try:
		user = User(email=data.email, password_hash=hash_password(data.password))
		session.add(user)
		session.flush()
	except:
		raise UserAlreadyExists("User already exists")
	try:
		profile = Profile(user_id=user.id)
		session.add(profile)
		session.flush()
	except Exception as error:
		raise Exception(error)
	return user

def read_user(user_id: int, session: Session):
	try:
		user = session.query(User).where(User.id == user_id).first()
	except:
		raise ErrorReadingUser("error reading user")
	return user

def update_user(user_id: int, data: userUpdate, session: Session):
	user = session.query(User).where(User.id == user_id).first()
	try:
		userData = data.model_dump(exclude_none=True, exclude_unset=True)
		for k, v in userData.items():
			if k == 'password':
				setattr(user, "password_hash", hash_password(v))
			if k == 'email':
				setattr(user, k, v)
				setattr(user, "is_verified", False)
			else:
				setattr(user, k, v)
		session.flush()
	except:
		raise ErrorUpdatingUser("error updating user")
	return user

def delete_user(user_id: int, session: Session):
	try:
		user = session.query(User).where(User.id == user_id).delete()
		session.flush()
	except:
		raise ErrorDeletingUser("error deleting user")
	return user
