from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select
from app.db.models import Song

# TODO: Add pagination
def read_songs(session: Session, limit: int = 10, page: int = 1):
	songs = session.query(Song).limit(limit=limit).all()
	return songs

def read_song(song_id: int, session: Session):
	song = session.query(Song).where(Song.id == song_id).first()
	return song


def search_songs(session: Session, *, q: str, artist: str, album: str,
                 provider: str, sort: str, order: str, page: int, page_size: int):
    """Search the shared catalog without contacting a provider or exposing playlists."""
    filters = []
    if q:
        filters.append(or_(*(column.icontains(q, autoescape=True)
                            for column in (Song.title, Song.artist, Song.album))))
    for column, value in ((Song.artist, artist), (Song.album, album)):
        if value:
            filters.append(column.icontains(value, autoescape=True))
    if provider:
        filters.append(Song.provider == provider)

    sort_column = {"title": func.lower(Song.title), "artist": func.lower(Song.artist),
                   "created_at": Song.created_at}[sort]
    ordering = [column.desc() if order == "desc" else column.asc()
                for column in (sort_column, Song.id)]
    total = session.scalar(select(func.count()).select_from(Song).where(*filters))
    items = session.scalars(select(Song).where(*filters).order_by(*ordering)
                            .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total,
            "total_pages": (total + page_size - 1) // page_size}
