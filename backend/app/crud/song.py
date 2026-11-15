from sqlalchemy.orm import Session
from app.db.models import Song

# TODO: Add pagination
def read_songs(session: Session, limit: int = 10, page: int = 1):
	songs = session.query(Song).limit(limit=limit).all()
	return songs

def read_song(song_id: int, session: Session):
	song = session.query(Song).where(Song.id == song_id).first()
	return song
