<<<<<<< HEAD
from app.db.models import User, Profile
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
<<<<<<< HEAD
<<<<<<< HEAD
from datetime import datetime, timezone
from app.auth.passwords import hash_password

class UserUpdate(BaseModel):
=======
from app.auth.passwords import hash_password

class userSignup(BaseModel):
	email: str
	password: str

class userUpdate(BaseModel):
>>>>>>> 1604070 (checkpoint)
=======
from datetime import datetime, timezone
from app.auth.passwords import hash_password

class UserUpdate(BaseModel):
>>>>>>> b344a7e (final)
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

<<<<<<< HEAD
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
<<<<<<< HEAD
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
=======
from app.db.models import User
from sqlalchemy.orm import Session
from pydantic import BaseModel

class UserSignup(BaseModel):
	email: str
	password: str

def create_user(session: Session, data: UserSignup):
	session.add(User(**UserSignup.model_dump()))
	session.flush()

def read_user(user: User):
	pass

def update_user(user: User):
	pass

def delete_user(user: User):
	pass
>>>>>>> 2c38698 (before rebase)
=======
		raise UserAlreadyExists("User already exists")
	try:
		profile = Profile(user_id=user.id)
		session.add(profile)
		session.flush()
	except Exception as error:
		raise Exception(error)
	return user

=======
>>>>>>> b344a7e (final)
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
<<<<<<< HEAD
	return user
>>>>>>> 1604070 (checkpoint)
=======
	return None
>>>>>>> b344a7e (final)
