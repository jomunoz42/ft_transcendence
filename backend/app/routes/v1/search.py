"""Authenticated PostgreSQL catalog search; the Spotify routes remain separate."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.current_user import current_user
from app.crud.song import search_songs
from app.db import get_session

router = APIRouter(dependencies=[Depends(current_user)])


class SongSearchParams(BaseModel):
    q: str = Field(default="", max_length=200)
    artist: str = Field(default="", max_length=200)
    album: str = Field(default="", max_length=200)
    provider: str = Field(default="", max_length=50)
    sort: Literal["title", "artist", "created_at"] = "title"
    order: Literal["asc", "desc"] = "asc"
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("q", "artist", "album", "provider")
    @classmethod
    def reject_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("NUL bytes are not allowed in search parameters")
        return value


class SongResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    artist: str
    album: str | None
    provider: str
    cover_url: str | None
    duration_ms: int | None
    created_at: datetime


class SongSearchResponse(BaseModel):
    items: list[SongResult]
    page: int
    page_size: int
    total: int
    total_pages: int


@router.get("/songs", response_model=SongSearchResponse)
def songs(params: Annotated[SongSearchParams, Query()],
          session: Session = Depends(get_session)):
    values = params.model_dump()
    for field in ("q", "artist", "album", "provider"):
        values[field] = values[field].strip()
    return search_songs(session, **values)
