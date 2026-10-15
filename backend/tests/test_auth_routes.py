"""Tests for the auth HTTP routes (issue #15): register, login, logout, me.

The seam is the HTTP API under /api/v1/auth, called through the real app.
"""

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
LOGOUT = "/api/v1/auth/logout"
COOKIE = "myplaylist_session"
ALICE = {"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"}


def test_register_returns_the_new_user(client):
    response = client.post(
        REGISTER, json={"email": " Alice@X.com ", "password": "hunter22", "display_name": "Alice"}
    )

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body == {"id": body["id"], "email": "alice@x.com", "display_name": "Alice"}


def test_register_with_an_invalid_field_says_which_field_and_why(client):
    response = client.post(
        REGISTER, json={"email": "not-an-email", "password": "hunter22", "display_name": "Alice"}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"field": "email", "reason": "not a valid email address"}}


def test_register_with_a_taken_email_is_a_conflict(client):
    client.post(REGISTER, json={"email": "alice@x.com", "password": "hunter22", "display_name": "Alice"})

    response = client.post(
        REGISTER, json={"email": "ALICE@x.com", "password": "other-pass", "display_name": "Alice 2"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}


def test_login_returns_the_user_and_sets_a_locked_down_session_cookie(client):
    user_id = client.post(REGISTER, json=ALICE).json()["id"]

    response = client.post(LOGIN, json={"email": "alice@x.com", "password": "hunter22"})

    assert response.status_code == 200
    assert response.json() == {"id": user_id, "email": "alice@x.com", "display_name": "Alice"}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("myplaylist_session=")
    flags = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert {"httponly", "secure", "samesite=lax", "max-age=604800"} <= flags


def test_me_after_login_returns_the_logged_in_user(client):
    user_id = client.post(REGISTER, json=ALICE).json()["id"]
    client.post(LOGIN, json={"email": "alice@x.com", "password": "hunter22"})

    response = client.get(ME)

    assert response.status_code == 200
    assert response.json() == {"id": user_id, "email": "alice@x.com", "display_name": "Alice"}


def test_me_without_a_session_cookie_is_refused(client):
    response = client.get(ME)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not logged in"}


def test_after_logout_a_copy_of_the_old_cookie_is_refused(client):
    client.post(REGISTER, json=ALICE)
    client.post(LOGIN, json={"email": "alice@x.com", "password": "hunter22"})
    stolen = client.cookies[COOKIE]

    response = client.post(LOGOUT)
    client.cookies.set(COOKIE, stolen)

    assert response.status_code == 204
    assert client.get(ME).status_code == 401


def test_logout_clears_the_session_cookie_from_the_browser(client):
    client.post(REGISTER, json=ALICE)
    client.post(LOGIN, json={"email": "alice@x.com", "password": "hunter22"})

    client.post(LOGOUT)

    assert COOKIE not in client.cookies


def test_wrong_password_and_unknown_email_get_the_identical_refusal(client):
    client.post(REGISTER, json=ALICE)

    wrong_password = client.post(LOGIN, json={"email": "alice@x.com", "password": "not-hers-1"})
    unknown_email = client.post(LOGIN, json={"email": "nobody@x.com", "password": "hunter22"})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": "Invalid email or password"}
    assert "set-cookie" not in wrong_password.headers
    assert "set-cookie" not in unknown_email.headers


def test_five_wrong_passwords_lock_the_account_even_for_the_right_one(client):
    client.post(REGISTER, json=ALICE)
    for _ in range(5):
        client.post(LOGIN, json={"email": "alice@x.com", "password": "not-hers-1"})

    response = client.post(LOGIN, json={"email": "alice@x.com", "password": "hunter22"})

    assert response.status_code == 401
