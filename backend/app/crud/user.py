from app.db.models import User, Profile
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.auth.passwords import hash_password

class userSignup(BaseModel):
	email: str
	password: str
	display_name: str | None

class UserAlreadyExists(Exception):
    pass
class ErrorCreatingProfile(Exception):
    pass

def create_user(session: Session, data: userSignup):
	try:
		user = User(email=data.email, password_hash=hash_password(data.password))
		session.add(user)
		session.flush()
	except:
		raise UserAlreadyExists("User already exists")
	try:
		session.add(Profile(user_id=user.id, display_name=data.display_name))
	except:
		session.rollback()
		raise ErrorCreatingProfile("Profile was not created")
	session.commit()
	return user

def update_user(user: User):
	pass

def delete_user(user: User):
	pass
