import pytest
from pydantic import BaseModel
from typing import Optional
from fastapi.testclient import TestClient
from fastapi import Depends
from app.main import app
from app.db.models import Song
from app.db import SessionLocal

client = TestClient(app, base_url="https://testserver")

COOKIE_NAME = "myplaylist_session"

def _login():
	res = client.post("/api/v1/auth/login", json={"email": "victor@edwed.com", "password": "wefgvwervrevrevver"})
	token = res.cookies.get(COOKIE_NAME)
	if token:
		client.cookies.set(COOKIE_NAME, token)
	return res

def _logout():
	client.post("/api/v1/auth/logout")
	client.cookies.delete(COOKIE_NAME)

@pytest.fixture(scope="module", autouse=True)                                
def login_once():                                                            
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
		Req(uri='/api/v1/profiles/2', method='GET'),
		Exp(status_code=200, body={"avatar_url": None, "display_name": "Luna", "bio": "Collecting books, playlists, and good memories.", "comments": [], "reactions": []}),
	),
	(
		Req(uri='/api/v1/profiles/2/comments', method='POST', body={"body": "Hello"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/2/comments/latest', method='POST', body={"body": "Bonjour"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/2/reactions', method='GET'),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/2/reactions', method='POST', body={"reaction": "like"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/2/reactions', method='POST', body={"reaction": "dislike"}),
		Exp(status_code=200),
	),
	(
		Req(uri='/api/v1/profiles/2/reactions', method='POST', body={"reaction": "bonjour"}),
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
]

def _do_request(session: TestClient, req: Req, exp: Exp):
	if (req.method == 'GET'):
		res = session.get(url=req.uri)
	if (req.method == 'POST'):
		res = session.post(url=req.uri, json=req.body)
	if (req.method == 'DELETE'):
		res = session.delete(url=req.uri)
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

	res = client.get("/api/v1/profiles/2")

	comments = res.json().get("comments")
	for c in comments:
		client.delete("/api/v1/profiles/2/comments/" + str(c.get("id")))

	reactions = res.json().get("comments")
	for r in reactions:
		client.delete("/api/v1/profiles/2/reactions")

	res = client.get("/api/v1/profiles/2")
	comments = res.json().get("comments")
	reactions = res.json().get("reactions")
	if (len(comments) > 0 or len(reactions) > 0):
		return 0

	res = client.post("/api/v1/profiles/me", json={"top10": []})
	res = client.get("/api/v1/profiles/me")
	top10s = res.json().get("top10_entries")
	if (len(top10s) > 0):
		return 0

	with SessionLocal() as session:
		session.query(Song).delete()
		session.commit()

	return 1

def test_cleaning():
	assert _clean() == 1
