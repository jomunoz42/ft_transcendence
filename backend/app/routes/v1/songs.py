from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_session
from app.db.models import User
from app.external.spotify.Spotify import Spotify
from app.crud.song import read_song, read_songs
from app.auth.current_user import current_user

router = APIRouter(dependencies=[Depends(current_user)])

@router.get("")
def get_songs(session: Session = Depends(get_session)):
	songs = read_songs(session)
	return songs

@router.get("/search")
def search_song(q: str = None, session: Session = Depends(get_session)):
	if q:
		spotify = Spotify()
		songs = spotify.search(q=q)
	else:
		songs = read_songs(session)
	return songs

@router.get("/{song_id}")
def get_song(song_id: int, session: Session = Depends(get_session)):
	song = read_song(song_id=song_id, session=session)
	return song
