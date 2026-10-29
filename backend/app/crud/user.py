from app.db.models import User, Profile
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from app.auth.passwords import hash_password

class UserUpdate(BaseModel):
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

def read_user(user_id: int, session: Session):
	try:
		user = session.query(User).where(User.id == user_id).first()
	except:
		raise ErrorReadingUser("error reading user")
	return user

def update_user(user_id: int, data: UserUpdate, session: Session):
	user = session.query(User).where(User.id == user_id).first()
	try:
		if data.password is not None:
			setattr(user, "password_hash", hash_password(data.password))
		if data.email is not None:
			setattr(user, "email", data.email)
			setattr(user, "is_verified", False)
		session.flush()
	except:
		raise ErrorUpdatingUser("error updating user")
	return user

def delete_user(user_id: int, session: Session):
	try:
		user = session.query(User).where(User.id == user_id).first()
		user.deleted_at = datetime.now(timezone.utc)
		session.flush()
	except:
		raise ErrorDeletingUser("error deleting user")
	return None
