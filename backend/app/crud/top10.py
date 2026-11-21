from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel
from typing import Literal
from app.db.models import Top10Entry, Song
from app import errors

class SongAdd(BaseModel):
	provider_id: str
	title: str
	artist: str
	album: str | None = None
	cover_url: str | None = None
	duration_ms: int | None = None

class Top10Add(BaseModel):
	song: SongAdd
	rank: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

class Top10Update(BaseModel):
	rank: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

def _get_or_create_song(song_data: SongAdd, session: Session) -> Song:
	song = session.query(Song).filter(
		and_(Song.provider == "spotify", Song.provider_id == song_data.provider_id)
	).first()
	if song is None:
		song = Song(
			provider="spotify",
			provider_id=song_data.provider_id,
			title=song_data.title,
			artist=song_data.artist,
			album=song_data.album,
			cover_url=song_data.cover_url,
			duration_ms=song_data.duration_ms,
		)
		session.add(song)
		session.flush()
	return song

def create_top10(user_id: int, data: Top10Add, session: Session) -> Top10Entry:
	# Check if user already has 10 entries
	count = session.query(Top10Entry).filter(Top10Entry.user_id == user_id).count()
	if count >= 10:
		raise errors.HTTP_409_CONFLICT
	song = _get_or_create_song(data.song, session)
	# Check if this user already has this song in their top10
	existing_song = session.query(Top10Entry).filter(
		and_(Top10Entry.user_id == user_id, Top10Entry.song_id == song.id)
	).first()
	if existing_song:
		raise errors.HTTP_409_CONFLICT
	# Check if this rank is already taken
	existing_rank = session.query(Top10Entry).filter(
		and_(Top10Entry.user_id == user_id, Top10Entry.rank == data.rank)
	).first()
	if existing_rank:
		raise errors.HTTP_409_CONFLICT
	entry = Top10Entry(user_id=user_id, song_id=song.id, rank=data.rank)
	session.add(entry)
	session.flush()
	return entry

def read_top10s(user_id: int, session: Session) -> list[Top10Entry]:
	return session.query(Top10Entry).filter(
		Top10Entry.user_id == user_id
	).order_by(Top10Entry.rank).all()

def read_top10(user_id: int, top10_id: int, session: Session) -> Top10Entry | None:
	return session.query(Top10Entry).filter(
		and_(Top10Entry.id == top10_id, Top10Entry.user_id == user_id)
	).first()

def update_top10(user_id: int, top10_id: int, data: Top10Update, session: Session) -> Top10Entry:
	entry = session.query(Top10Entry).filter(
		and_(Top10Entry.id == top10_id, Top10Entry.user_id == user_id)
	).first()
	if not entry:
		raise errors.HTTP_404_NOT_FOUND
	if entry.rank == data.rank:
		return entry
	# If another entry has this rank, swap them
	other = session.query(Top10Entry).filter(
		and_(Top10Entry.user_id == user_id, Top10Entry.rank == data.rank)
	).first()
	if other:
		other.rank = entry.rank
		session.flush()
	entry.rank = data.rank
	session.flush()
	return entry

def delete_top10(user_id: int, top10_id: int, session: Session):
	entry = session.query(Top10Entry).filter(
		and_(Top10Entry.id == top10_id, Top10Entry.user_id == user_id)
	).first()
	if not entry:
		raise errors.HTTP_404_NOT_FOUND
	session.delete(entry)
	session.flush()
