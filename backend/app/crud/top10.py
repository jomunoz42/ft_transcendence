from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, case, update
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
		try:
			with session.begin_nested():
				session.add(song)
				session.flush()
		except IntegrityError:
			song = session.query(Song).filter(
				and_(Song.provider == "spotify", Song.provider_id == song_data.provider_id)
			).first()
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
	try:
		with session.begin_nested():
			session.add(entry)
			session.flush()
	except IntegrityError:
		raise errors.HTTP_409_CONFLICT
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
	"""Move one of the user's entries to `data.rank`; if that rank is taken, the two entries swap ranks.

	Both entries keep their ids. All the user's entries are locked in id order first, so concurrent
	moves on the same Top 10 wait for each other instead of deadlocking. 404 if the entry is not the
	user's; 409 if a concurrent add takes the target rank first.
	"""
	entries = session.query(Top10Entry).filter(Top10Entry.user_id == user_id).order_by(Top10Entry.id).populate_existing().with_for_update().all()
	entry = next((e for e in entries if e.id == top10_id), None)
	if not entry:
		raise errors.HTTP_404_NOT_FOUND
	if entry.rank == data.rank:
		return entry
	new_rank_by_id = {entry.id: data.rank}
	other = next((e for e in entries if e.rank == data.rank), None)
	if other:
		new_rank_by_id[other.id] = entry.rank
	try:
		with session.begin_nested():
			session.execute(update(Top10Entry).where(Top10Entry.id.in_(new_rank_by_id)).values(rank=case(new_rank_by_id, value=Top10Entry.id)))
	except IntegrityError:
		raise errors.HTTP_409_CONFLICT
	return entry

def delete_top10(user_id: int, top10_id: int, session: Session):
	entry = session.query(Top10Entry).filter(
		and_(Top10Entry.id == top10_id, Top10Entry.user_id == user_id)
	).populate_existing().with_for_update().first()
	if not entry:
		raise errors.HTTP_404_NOT_FOUND
	session.delete(entry)
	session.flush()
