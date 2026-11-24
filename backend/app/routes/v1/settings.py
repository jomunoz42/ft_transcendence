from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.current_user import current_user
from app.crud.user import UserUpdate, update_user
from app.db import _me, get_session
from app.db.models import User

router = APIRouter()


@router.get("")
def get_me(current_user: User = Depends(current_user)):
    return _me(current_user)


@router.post("")
def update_me(data: UserUpdate, current_user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = update_user(user_id=current_user.id, data=data, session=session)
    session.commit()
    return _me(user)
