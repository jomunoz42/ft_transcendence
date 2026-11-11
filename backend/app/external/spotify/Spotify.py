import requests, os
from dotenv import load_dotenv
from pydantic import BaseModel
from app.db.models import Song
load_dotenv()

ACCOUNT_BASE_URL = 'https://accounts.spotify.com'
BASE_URL = 'https://api.spotify.com'

class SpotifyTrack(BaseModel):
	album: dict
	artists: list
	disc_number: int
	duration_ms: int
	explicit: bool
	external_ids: dict
	external_urls: dict
	href: str
	id: str
	is_playable: bool
	name: str
	track_number: int
	type: str
	uri: str
	is_local: bool

def song_model_mapping(track: SpotifyTrack):
	return Song(
		provider="spotify",
		provider_id=track.id,
		title=track.name,
		artist=track.artists[0].get("name"),
		album=track.album.get("name"),
		cover_url=track.album.get("images")[0]["url"],
		duration_ms=track.duration_ms,
		metadata_=track.model_dump(),
	)

class Spotify():
	def __init__(self):
		self.session: requests.Session = self.get_session()

	def get_session(self):
		data = {
			'grant_type': 'client_credentials',
			'client_id': os.environ["SPOTIFY_CLIENT_ID"],
			'client_secret': os.environ["SPOTIFY_CLIENT_SECRET"],
		}

		res = requests.post(ACCOUNT_BASE_URL + '/api/token', data=data)
		auth = res.json()
		session = requests.Session()
		session.headers.update({
			'Authorization': f'{auth.get('token_type')} {auth.get('access_token')}'
		})
		return session

	def search(self, q: str) -> list[Song]:
		params = {
			'q': q,
			'type': 'track',
			'limit': 10,
		}
		res  = self.session.get(BASE_URL + '/v1/search', params=params)
		tracks = res.json().get("tracks")
		return [song_model_mapping(SpotifyTrack.model_validate(i)) for i in tracks.get("items")]
