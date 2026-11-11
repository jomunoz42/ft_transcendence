from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_session
from app.db.models import User
from app.external.spotify.Spotify import Spotify
from app.crud.song import read_song, read_songs
from app.auth.current_user import current_user

router = APIRouter()
spotify = Spotify()

@router.get("")
def get_songs(session: Session = Depends(get_session), me: User = Depends(current_user)):
	try:
		songs = read_songs(session)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return songs

@router.get("/search")
def search_song(q: str = None, session: Session = Depends(get_session), me: User = Depends(current_user)):
	try:
		if q:
			songs = spotify.search(q=q)
		else:
			songs = read_songs(session)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return songs

@router.get("/{song_id}")
def get_song(song_id: int, session: Session = Depends(get_session), me: User = Depends(current_user)):
	try:
		song = read_song(song_id=song_id, session=session)
	except Exception as error:
		raise HTTPException(status_code=400, detail=str(error))
	return song
