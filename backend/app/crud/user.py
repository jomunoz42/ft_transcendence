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
