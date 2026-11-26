"""Avatar upload, serving, default and deletion over HTTP, against real Postgres."""

import datetime
import io

import pytest
from PIL import Image

from app.auth.constants import SESSION_COOKIE_NAME
from app.auth.sessions import start_session
from sqlalchemy import delete, func, select

from app.db.models import Avatar, Block, Profile, User

DEFAULT_URL = "/api/v1/avatars/default"
UPLOAD = "/api/v1/profiles/me/avatar"


def image_bytes(fmt, size=(600, 400), exif=None, color=(200, 30, 30)):
    buffer = io.BytesIO()
    extra = {"exif": exif} if exif is not None else {}
    Image.new("RGB", size, color).save(buffer, fmt, **extra)
    return buffer.getvalue()


def upload(client, data, name="avatar.png", content_type="image/png"):
    return client.put(UPLOAD, files={"file": (name, data, content_type)})


def make_user(session, email):
    user = User(email=email, password_hash="unused")
    user.profile = Profile(display_name=email.split("@")[0])
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def alice(session, client):
    user = make_user(session, "alice@avatar.test")
    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, user))
    session.commit()
    return user


def test_a_new_user_shows_the_default_avatar(client, alice):
    assert client.get("/api/v1/profiles/me").json()["avatar_url"] == DEFAULT_URL

    response = client.get(DEFAULT_URL)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.content.startswith(b"<svg")


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_an_uploaded_avatar_is_served_as_a_256_square_webp_without_exif(client, alice, fmt):
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"
    original = image_bytes(fmt, exif=exif)
    assert b"SecretCameraMaker" in original

    response = upload(client, original, name=f"me.{fmt.lower()}", content_type=f"image/{fmt.lower()}")
    assert response.status_code == 200
    url = response.json()["avatar_url"]
    assert url.startswith(f"/api/v1/avatars/{alice.id}?v=")
    assert client.get("/api/v1/profiles/me").json()["avatar_url"] == url

    served = client.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert b"SecretCameraMaker" not in served.content
    image = Image.open(io.BytesIO(served.content))
    assert (image.format, image.size) == ("WEBP", (256, 256))
    assert not image.getexif()


def test_a_new_upload_changes_the_url_so_browsers_fetch_it_again(client, alice):
    first = upload(client, image_bytes("PNG")).json()["avatar_url"]
    second = upload(client, image_bytes("PNG", color=(30, 30, 200))).json()["avatar_url"]
    assert first != second
    assert client.get(second).status_code == 200


def test_avatars_need_a_login(client, alice):
    upload(client, image_bytes("PNG"))
    client.cookies.clear()
    assert upload(client, image_bytes("PNG")).status_code == 401
    assert client.delete(UPLOAD).status_code == 401
    assert client.get(f"/api/v1/avatars/{alice.id}").status_code == 401


def assert_nothing_stored(client, user):
    assert client.get("/api/v1/profiles/me").json()["avatar_url"] == DEFAULT_URL
    assert client.get(f"/api/v1/avatars/{user.id}").status_code == 404


def test_a_file_over_2_mb_is_too_large(client, alice):
    assert upload(client, b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    assert_nothing_stored(client, alice)


def test_a_small_file_with_too_many_pixels_is_too_large_before_it_is_decoded(client, alice):
    bomb = image_bytes("PNG", size=(6000, 5000))
    assert len(bomb) < 2 * 1024 * 1024
    assert upload(client, bomb).status_code == 413
    assert_nothing_stored(client, alice)


@pytest.mark.parametrize("name,data", [
    ("gif", image_bytes("GIF")),
    ("text named png", b"<script>alert(1)</script>"),
    ("truncated png", image_bytes("PNG")[:200]),
    ("empty", b""),
])
def test_anything_but_a_readable_png_jpeg_or_webp_is_refused(client, alice, name, data):
    assert upload(client, data).status_code == 415
    assert_nothing_stored(client, alice)


def test_deleting_my_avatar_shows_the_default_again(client, alice):
    old_url = upload(client, image_bytes("PNG")).json()["avatar_url"]

    response = client.delete(UPLOAD)
    assert response.status_code == 200
    assert response.json() == {"avatar_url": DEFAULT_URL}
    assert client.get(old_url).status_code == 404
    assert_nothing_stored(client, alice)

    assert client.delete(UPLOAD).json() == {"avatar_url": DEFAULT_URL}


def test_avatar_url_cannot_be_set_by_hand(client, alice):
    assert client.post("/api/v1/profiles/me", json={"avatar_url": "https://tracker.example/pixel.png"}).status_code == 200
    assert client.get("/api/v1/profiles/me").json()["avatar_url"] == DEFAULT_URL


def test_other_users_see_my_avatar_on_my_profile_and_can_load_it(session, client, alice):
    url = upload(client, image_bytes("PNG")).json()["avatar_url"]
    bob = make_user(session, "bob@avatar.test")
    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, bob))
    session.commit()

    assert client.get(f"/api/v1/profiles/{alice.id}").json()["avatar_url"] == url
    listed = {p["display_name"]: p["avatar_url"] for p in client.get("/api/v1/profiles").json()}
    assert (listed["alice"], listed["bob"]) == (url, DEFAULT_URL)
    assert client.get(url).status_code == 200


def test_deleting_the_user_deletes_their_avatar(session, client, alice):
    upload(client, image_bytes("PNG"))
    session.execute(delete(User).where(User.id == alice.id))
    assert session.scalar(select(func.count()).select_from(Avatar).where(Avatar.user_id == alice.id)) == 0


def test_a_deleted_account_avatar_is_no_longer_served(session, client, alice):
    url = upload(client, image_bytes("PNG")).json()["avatar_url"]
    bob = make_user(session, "bob@avatar.test")
    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, bob))
    alice.deleted_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()
    assert client.get(url).status_code == 404


def test_an_uploaded_avatar_is_never_cached_but_the_default_is(client, alice):
    url = upload(client, image_bytes("PNG")).json()["avatar_url"]

    assert client.get(url).headers["cache-control"] == "private, no-store"
    assert client.get(DEFAULT_URL).headers["cache-control"] == "public, max-age=86400"


@pytest.mark.parametrize("alice_blocks", [True, False], ids=["alice blocks bob", "bob blocks alice"])
def test_a_block_either_way_hides_the_avatar(session, client, alice, alice_blocks):
    url = upload(client, image_bytes("PNG")).json()["avatar_url"]
    bob = make_user(session, "bob@avatar.test")
    blocker, blocked = (alice, bob) if alice_blocks else (bob, alice)
    session.add(Block(blocker_id=blocker.id, blocked_id=blocked.id))
    client.cookies.set(SESSION_COOKIE_NAME, start_session(session, bob))
    session.commit()

    assert client.get(url).status_code == 404
