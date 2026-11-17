import pytest
from functools import cache
from pydantic import BaseModel
from typing import Optional
from fastapi.testclient import TestClient
from fastapi import Depends
from app.main import app
from app.db.models import Profile, Song, Top10Entry, User
from app.db import SessionLocal

client = TestClient(app, base_url="https://testserver")

COOKIE_NAME = "myplaylist_session"
VICTOR_EMAIL = "victor@edwed.com"

@cache
def _luna_id() -> int:
	"""Return Luna's user id. Looked up by display name because ids change on every reseed."""
	with SessionLocal() as session:
		user_id = session.query(Profile.user_id).filter(Profile.display_name == "Luna").scalar()
	assert user_id is not None, "seed user Luna is missing, run make sample"
	return user_id

@cache
def _victor_id() -> int:
	"""Return the user id of Victor, the account these tests log in as."""
	with SessionLocal() as session:
		return session.query(User.id).filter(User.email == VICTOR_EMAIL).scalar()

def _delete_victor_top10():
	"""Delete Victor's top 10 and the song the tests create, so a run never depends on the previous one."""
	with SessionLocal() as session:
		session.query(Top10Entry).filter(Top10Entry.user_id == _victor_id()).delete()
		session.query(Song).filter(Song.title == "Hello", Song.artist == "bonjour").delete()
		session.commit()

def _login():
	res = client.post("/api/v1/auth/login", json={"email": VICTOR_EMAIL, "password": "wefgvwervrevrevver"})
	token = res.cookies.get(COOKIE_NAME)
	if token:
		client.cookies.set(COOKIE_NAME, token)
	return res

def _logout():
	client.post("/api/v1/auth/logout")
	client.cookies.delete(COOKIE_NAME)

@pytest.fixture(scope="module", autouse=True)                                
def login_once():
	_delete_victor_top10()
	_login()                                                              
	yield                                                                    
	_logout()

class Req(BaseModel):
	uri: str
	method: str
	body: Optional[dict] = None

class Exp(BaseModel):
	status_code: int
	body: Optional[dict] | Optional[list] = None

tests = [
	(
		Req(uri='/api/v1/settings', method='GET'),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/settings', method='POST', body={"email": "victor.barre@newemail.com"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/settings', method='GET'),
		Exp(status_code=200, body={"email": "victor.barre@newemail.com"}),
	),
	(
		Req(uri='/api/v1/settings', method='POST', body={"email": "victor@edwed.com"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/settings', method='GET'),
		Exp(status_code=200, body={"email": "victor@edwed.com"}),
	),
	(
		Req(uri='/api/v1/profiles', method='GET'),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/me', method='GET'),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/{luna}', method='GET'),
		Exp(status_code=200, body={"avatar_url": None, "display_name": "Luna", "bio": "Collecting books, playlists, and good memories.", "comments": [], "reactions": []}),
	),
	(
		Req(uri='/api/v1/profiles/{luna}/comments', method='POST', body={"body": "Hello"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/{luna}/comments/latest', method='POST', body={"body": "Bonjour"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/{luna}/reactions', method='GET'),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/{luna}/reactions', method='POST', body={"reaction": "like"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/{luna}/reactions', method='POST', body={"reaction": "dislike"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/{luna}/reactions', method='POST', body={"reaction": "bonjour"}),
		Exp(status_code=422),
	),
	(
		Req(uri='/api/v1/profiles/me', method='GET'),
		Exp(status_code=200, body={"display_name": "Victor", "avatar_url": None}),
	),
	(
		Req(uri='/api/v1/profiles/me', method='POST', body={"display_name": "bonjour"}),
		Exp(status_code=200, body={"display_name": "bonjour"}),
	),
	(
		Req(uri='/api/v1/profiles/me', method='POST', body={"display_name": "Victor"}),
		Exp(status_code=200, body={"display_name": "Victor"}),
	),
	(
		Req(uri='/api/v1/profiles/me', method='POST', body={"Victor": "display_name"}),
		Exp(status_code=200, body={"display_name": "Victor"}),
	),
	(
		Req(uri='/api/v1/profiles/me', method='POST', body={"top10": [{"title": "Hello", "artist": "bonjour", "rank": 1}]}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/me', method='POST', body={"top10": [{"title": "Hello", "artist": "bonjour", "rank": 1}]}),
		Exp(status_code=400),
	),
	(
		Req(uri='/api/v1/songs', method='GET'),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/songs/search', method='GET'),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/songs/search?q=tupac', method='GET'),
		Exp(status_code=200),
	),
]

def _do_request(session: TestClient, req: Req, exp: Exp):
	uri = req.uri.format(luna=_luna_id())
	if (req.method == 'GET'):
		res = session.get(url=uri)
	if (req.method == 'POST'):
		res = session.post(url=uri, json=req.body)
	if (req.method == 'DELETE'):
		res = session.delete(url=uri)
	assert res.status_code == exp.status_code
	if (exp.body is not None and str(res.status_code).startswith("2")):
		if isinstance(exp.body, dict):
			for k, v in exp.body.items():
				assert res.json().get(k) == exp.body.get(k)
		if isinstance(exp.body, list):
			assert len(exp.body) == len(res.json())



@pytest.mark.parametrize('req,exp', tests)
def test_backend_authorized(req, exp):
	_do_request(session=client, req=req, exp=exp)

@pytest.mark.parametrize('req,exp', tests)
def test_backend_unauthorized(req, exp):
	_logout()
	exp.status_code = 401
	_do_request(session=client, req=req, exp=exp)

def test_auth():
	res = _login()
	assert res.status_code == 200
	res = client.get("/api/v1/settings")
	assert res.status_code == 200
	_logout()
	res = client.get("/api/v1/settings")
	assert res.status_code == 401

def _clean():
	_login()
	luna = f"/api/v1/profiles/{_luna_id()}"

	victor = _victor_id()

	res = client.get(f"{luna}/comments")
	assert res.status_code == 200, f"GET {luna}/comments returned {res.status_code}"
	for c in res.json():
		if c.get("author_id") == victor:
			client.delete(f"{luna}/comments/" + str(c.get("id")))
	client.delete(f"{luna}/reactions")

	comments = client.get(f"{luna}/comments").json()
	reactions = client.get(f"{luna}/reactions").json()
	if any(x.get("author_id") == victor for x in comments + reactions):
		return 0

	_delete_victor_top10()

	return 1

def test_cleaning():
	assert _clean() == 1
