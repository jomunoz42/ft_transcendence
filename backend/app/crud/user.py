from app.db.models import User, Profile
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.auth.passwords import hash_password

class UserUpdate(BaseModel):
	email: Optional[str] = None
	password: Optional[str] = None

def read_user(user_id: int, session: Session):
	return session.query(User).where(User.id == user_id).first()

def update_user(user_id: int, data: UserUpdate, session: Session):
	user = session.query(User).where(User.id == user_id).first()
	if data.password is not None:
		setattr(user, "password_hash", hash_password(data.password))
	if data.email is not None:
		setattr(user, "email", data.email)
		setattr(user, "is_verified", False)
	session.flush()
	return user
