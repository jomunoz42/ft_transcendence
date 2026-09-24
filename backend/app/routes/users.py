from fastapi import APIRouter
from app.db.models import User
from pydantic import BaseModel

class UserCreate(BaseModel):
	username: str

router = APIRouter()

################################################
# me
################################################

@router.get("/me")
def get_me():
	return {"username": "vicky"}

@router.post("/me")
def post_me(data: UserCreate):
	return {"username": data.username}

@router.patch("/me")
def patch_me(data: UserCreate):
	return {"username": data.username}

################################################
# others
################################################

@router.get(f"/{id}")
def get_users():
	return {"username": id}
