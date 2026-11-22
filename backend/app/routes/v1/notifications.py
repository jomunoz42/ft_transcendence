"""Authenticated notification reads; only the mutation route commits."""

import datetime

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.current_user import current_user
from app.crud.notification import DEFAULT_LIMIT, MAX_LIMIT, MAX_OFFSET, list_notifications, mark_as_read, unread_count
from app.db import get_session
from app.db.models import User

router = APIRouter()


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    event_type: str
    message: str
    created_at: datetime.datetime
    read_at: datetime.datetime | None


@router.get("", response_model=list[NotificationResponse])
def notifications(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    me: User = Depends(current_user), session: Session = Depends(get_session),
):
    return list_notifications(session, me.id, limit=limit, offset=offset)


@router.get("/unread-count")
def count(me: User = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return {"unread_count": unread_count(session, me.id)}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read(
    notification_id: int = Path(ge=1, le=2**63 - 1),
    me: User = Depends(current_user), session: Session = Depends(get_session),
):
    notification = mark_as_read(session, me.id, notification_id)
    session.commit()
    return notification
