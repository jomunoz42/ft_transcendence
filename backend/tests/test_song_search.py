"""Search HTTP contract against real PostgreSQL, with rollback-only fixtures."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import end_session, start_session
from app.db.models import Profile, Song, Top10Entry, User, UserSession
from app.external.spotify.Spotify import Spotify

URL = "/api/v1/search/songs"
PROVIDER = "search-test"


@pytest.fixture
def authenticated(session, client):
    user = User(email="catalog-search@example.test", password_hash="unused")
    session.add(user)
    session.flush()
    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, user))
    session.commit()
    return user


@pytest.fixture
def catalog(session, authenticated):
    rows = [
        Song(provider=PROVIDER, provider_id="1", title="zebra", artist="Alpha",
             album="Evening", metadata_={"private_provider_payload": True}),
        Song(provider=PROVIDER, provider_id="2", title="Alpha", artist="Beta", album=None),
        Song(provider=PROVIDER, provider_id="3", title="alpha", artist="alpha", album="Morning"),
        Song(provider=PROVIDER, provider_id="4", title="100%_pure/\\", artist="Gamma", album="Evening"),
        Song(provider="search-other", provider_id="1", title="zebra", artist="Alpha", album="Evening"),
    ]
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for index, row in enumerate(rows):
        row.created_at = start + timedelta(days=index // 2)
    session.add_all(rows)
    session.commit()
    return rows


def search(client, **params):
    response = client.get(URL, params={"provider": PROVIDER, **params})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("state", ["missing", "invalid", "expired", "revoked", "deleted"])
def test_requires_live_session(session, client, authenticated, state):
    token = client.cookies.get(SESSION_COOKIE_NAME)
    if state == "missing":
        client.cookies.clear()
    elif state == "invalid":
        client.cookies.set(SESSION_COOKIE_NAME, "invalid")
    elif state == "expired":
        session.scalar(select(UserSession).where(UserSession.user_id == authenticated.id)).expires_at = (
            datetime.now(timezone.utc) - timedelta(days=1)
        )
    elif state == "revoked":
        end_session(session, token)
    else:
        authenticated.deleted_at = datetime.now(timezone.utc)
    session.commit()
    assert client.get(URL).status_code == 401


@pytest.mark.parametrize("params,indices", [
    ({"q": " ZEBRA "}, [0]),
    ({"q": "BETA"}, [1]),
    ({"q": "morning"}, [2]),
    ({"artist": " ALPHA "}, [2, 0]),
    ({"album": " eve "}, [3, 0]),
    ({"q": "zebra", "artist": "alpha", "album": "evening"}, [0]),
    ({"q": "zebra", "artist": "Beta"}, []),
    ({"provider": "search-other"}, [4]),
    ({"provider": "SEARCH-OTHER"}, []),
    ({"provider": "does-not-exist"}, []),
])
def test_text_and_filters_are_combined_before_pagination(client, catalog, params, indices):
    result = search(client, **params)
    assert [row["id"] for row in result["items"]] == [catalog[index].id for index in indices]
    assert result["total"] == len(indices)
    assert result["total_pages"] == (1 if indices else 0)


@pytest.mark.parametrize("q", ["%", "_", "/", "\\", "100%_pure/\\"])
def test_search_treats_wildcards_and_escape_characters_literally(client, catalog, q):
    assert [row["id"] for row in search(client, q=q)["items"]] == [catalog[3].id]


@pytest.mark.parametrize("field", ["artist", "album"])
def test_filters_escape_wildcards(client, catalog, field):
    assert search(client, **{field: "%"})["items"] == []


@pytest.mark.parametrize("sort,indices", [
    ("title", [3, 1, 2, 0]),
    ("artist", [0, 2, 1, 3]),
    ("created_at", [0, 1, 2, 3]),
])
@pytest.mark.parametrize("order", ["asc", "desc"])
def test_all_sorts_use_unique_id_tiebreaker(client, catalog, sort, indices, order):
    expected = [catalog[index].id for index in indices]
    if order == "desc":
        expected.reverse()
    pages = [search(client, sort=sort, order=order, page=page, page_size=1)
             for page in range(1, 5)]
    assert [page["items"][0]["id"] for page in pages] == expected
    assert all(page["total"] == 4 and page["total_pages"] == 4 for page in pages)
    assert search(client, sort=sort, order=order, page=2, page_size=1) == pages[1]


def test_default_maximum_and_last_pages(session, client, authenticated):
    session.add_all([Song(provider=PROVIDER, provider_id=str(index), title="Tie", artist="Tie")
                     for index in range(105)])
    session.commit()
    first = search(client)
    assert (len(first["items"]), first["page"], first["page_size"], first["total_pages"]) == (20, 1, 20, 6)
    all_ids = [row["id"] for page in range(1, 7) for row in search(client, page=page)["items"]]
    assert len(all_ids) == len(set(all_ids)) == 105
    assert all_ids == sorted(all_ids)
    assert len(search(client, page_size=100)["items"]) == 100
    assert len(search(client, page=6)["items"]) == 5
    assert search(client, page=10_000, page_size=100) == {
        "items": [], "page": 10_000, "page_size": 100, "total": 105, "total_pages": 2,
    }


def test_whitespace_and_empty_filters_browse_catalog(client, catalog):
    assert search(client, q="  ", artist="\t", album=" ") == search(client)
    result = search(client, provider=" ", q="zebra")
    assert {row["id"] for row in result["items"]} == {catalog[0].id, catalog[4].id}


def test_empty_results_and_out_of_range_filtered_page(client, catalog):
    assert search(client, q="no-such-song") == {
        "items": [], "page": 1, "page_size": 20, "total": 0, "total_pages": 0,
    }
    result = search(client, artist="Alpha", page_size=1, page=3)
    assert (result["items"], result["total"], result["total_pages"]) == ([], 2, 2)


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": -1}, {"page": 10_001}, {"page": "abc"}, {"page": "1.5"},
    {"page_size": 0}, {"page_size": -1}, {"page_size": 101}, {"page_size": "abc"},
    {"sort": "album"}, {"sort": "title; DROP TABLE songs"}, {"order": "up"},
    {"q": "x" * 201}, {"artist": "x" * 201}, {"album": "x" * 201}, {"provider": "x" * 51},
])
def test_invalid_parameters_return_422(client, authenticated, params):
    assert client.get(URL, params=params).status_code == 422


@pytest.mark.parametrize("field", ["q", "artist", "album", "provider"])
def test_nul_in_search_parameters_returns_422(client, authenticated, field):
    response = client.get(URL, params={field: "a\x00b"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", field]


def test_response_is_explicit_and_search_never_calls_spotify_or_writes(session, client, catalog, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Local search must not contact Spotify")

    monkeypatch.setattr(Spotify, "get_session", unexpected)
    before = session.scalar(select(func.count()).select_from(Song))
    result = search(client, q="zebra")
    assert set(result["items"][0]) == {
        "id", "title", "artist", "album", "provider", "cover_url", "duration_ms", "created_at",
    }
    assert session.scalar(select(func.count()).select_from(Song)) == before


def test_private_top10_song_is_searchable_without_exposing_its_owner(session, client, catalog):
    owner = User(email="private-list-owner@example.test", password_hash="unused")
    profile = Profile(user=owner, display_name="Private list owner", is_top10_public=False)
    entry = Top10Entry(user=owner, song=catalog[0], rank=1)
    session.add_all([profile, entry])
    session.commit()

    result = search(client, q="zebra")
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == catalog[0].id
    assert set(result["items"][0]) == {
        "id", "title", "artist", "album", "provider", "cover_url", "duration_ms", "created_at",
    }
    payload = json.dumps(result)
    assert owner.email not in payload
    assert profile.display_name not in payload
    assert all(field not in payload for field in ("user_id", "top10_entries", "rank", "is_top10_public"))


def test_legacy_song_routes_keep_their_array_and_spotify_contracts(client, catalog, monkeypatch):
    calls = []
    monkeypatch.setattr(Spotify, "get_session", lambda self: None)
    monkeypatch.setattr(Spotify, "search", lambda self, q: calls.append(q) or [catalog[0]])
    assert isinstance(client.get("/api/v1/songs").json(), list)
    assert isinstance(client.get("/api/v1/songs/search").json(), list)
    result = client.get("/api/v1/songs/search", params={"q": "zebra"})
    assert result.status_code == 200
    assert isinstance(result.json(), list)
    assert calls == ["zebra"]
