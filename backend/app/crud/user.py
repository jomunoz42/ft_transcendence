from app.db.models import User, Profile
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.exc import IntegrityError
from app.auth.passwords import hash_password
from app.auth.registration import check_email, check_password
from app import errors

class UserUpdate(BaseModel):
	email: Optional[str] = None
	password: Optional[str] = None

def read_user(user_id: int, session: Session):
	return session.query(User).where(User.id == user_id).first()

def update_user(user_id: int, data: UserUpdate, session: Session):
	"""Change the user's email and/or password with the same rules as registration. Raises 422 on bad input, 409 if the email is taken; never commits."""
	email = check_email(data.email) if data.email is not None else None
	if data.password is not None:
		check_password(data.password)
	user = session.query(User).where(User.id == user_id).first()
	session.flush()
	try:
		with session.begin_nested():
			if data.password is not None:
				user.password_hash = hash_password(data.password)
			if email is not None:
				user.email = email
				user.is_verified = False
	except IntegrityError:
		raise errors.HTTP_409_EMAIL_TAKEN from None
	return user
