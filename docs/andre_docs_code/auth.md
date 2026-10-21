# André's code docs — Auth

Code lives in `backend/app/auth/`. For why it is built this way, see
[`whys.md`](whys.md#auth). New functions are added here as auth features land.

## Passwords — `app.auth.passwords`

```python
from app.auth.passwords import hash_password, verify_password

user.password_hash = hash_password("hunter22")   # Argon2, salted

if not verify_password(typed_password, user.password_hash):
    ...  # login failed
```

- `hash_password(password) -> str`: returns a new string every time, even for the
  same password, because the salt is random. The salt is stored inside that string,
  so it needs no separate column.
- `verify_password(password, password_hash) -> bool`: `True` or `False`, **never
  raises**. A wrong password and a corrupt stored hash both give `False`.

Never store, log, or compare plain passwords anywhere else.

## Registration — `app.auth.registration`

```python
from app.auth.registration import EmailTaken, InvalidRegistration, register_user

try:
    user = register_user(session, email, password, display_name)
    session.commit()
except EmailTaken:
    ...  # 409: email already registered
except InvalidRegistration as error:
    ...  # 422: error.field ("email", "password", "display_name") and error.reason
```

- `register_user(session, email, password, display_name) -> User`: creates the
  user and their profile together. It flushes but **does not commit**; the caller
  commits.
- Email must be ASCII. It is stripped and lowercased before it is stored, so
  `A@x.com` and `a@x.com` are the same account. Password must be 8–128 characters and is never stripped.
  Display name is stripped and cannot be blank.
- After `EmailTaken` or `InvalidRegistration`, nothing was written and the session
  is still usable.
- A soft-deleted user's email stays taken. Freeing it (by anonymizing the email on
  GDPR delete) is decided for later, not built.

## Sessions — `app.auth.sessions`

```python
from app.auth.sessions import end_session, start_session, user_for_token

token = start_session(session, user)      # at login; put token in the cookie
session.commit()

user = user_for_token(session, token)     # on every request; None = not logged in

end_session(session, token)               # at logout
session.commit()
```

- `start_session(session, user) -> str`: the raw token goes only to the cookie.
  The database stores its SHA-256 hash. Each login is its own session, so a
  laptop and a phone stay logged in independently. It also deletes that user's
  expired sessions, so dead rows do not pile up.
- `user_for_token(session, token) -> User | None`: `None` when the token is
  missing, unknown, expired (exactly 168 hours, `SESSION_LIFETIME`), or the user is
  soft-deleted.
- `end_session(session, token)`: logs that one token out. Unknown or
  already-ended tokens are ignored, so logging out twice is fine.
- None of them commit; the caller does.

## Login — `app.auth.login`

```python
from app.auth.login import InvalidCredentials, authenticate

try:
    user = authenticate(session, email, password)
except InvalidCredentials:
    session.commit()          # keep the failed-attempt count, or lockout never triggers
    ...                       # 401, same message for every reason
token = start_session(session, user)
session.commit()
```

- `authenticate(session, email, password) -> User`: the email is matched
  whatever its case or surrounding spaces.
- Unknown email, wrong password, locked account, and deleted account all raise
  the same `InvalidCredentials`, and take the same time, so nobody can learn
  which emails exist.
- 5 wrong passwords lock the account for 15 minutes (`MAX_FAILED_ATTEMPTS`,
  `LOCKOUT`). Attempts during the lock are refused and not counted. After it,
  the user has 5 fresh tries. A correct password resets the count.

## Who is logged in — `app.auth.current_user`

```python
from fastapi import Depends
from app.auth.current_user import current_user
from app.db.models import User

@router.get("/something")
def something(user: User = Depends(current_user)):
    ...  # only runs for a logged-in user
```

- Reads the session cookie and returns the logged-in `User`. Missing, unknown or
  expired cookie: the request stops with 401 `{"detail": "Not logged in"}`, and
  the route body never runs.
- Use it on every route that needs a logged-in user. Do not read the cookie yourself.
- The cookie name is `SESSION_COOKIE_NAME` in `app.auth.constants`
  (`"myplaylist_session"`). The WebSocket login reads the same cookie.

## HTTP routes — `/api/v1/auth`

| Route | Body | Success | Errors |
|---|---|---|---|
| `POST /register` | `{email, password, display_name}` | 201 user | 422, 409 |
| `POST /login` | `{email, password}` | 200 user + cookie set | 401 |
| `GET /me` | none | 200 user | 401 |
| `POST /logout` | none | 204, cookie cleared | none |

"user" is always `{"id", "email", "display_name"}`. The password hash is never sent.

**Errors** use FastAPI's `{"detail": ...}`:
- 422 from a broken rule: `{"detail": {"field": "email", "reason": "not a valid email address"}}`.
  A missing or wrongly typed field gets FastAPI's own 422 instead, where `detail`
  is a list.
- 409: `{"detail": "Email already registered"}`.
- 401 from login: `{"detail": "Invalid email or password"}`, the same for every
  reason, including a locked account.

**The cookie:** `myplaylist_session`, `HttpOnly`, `Secure`, `SameSite=Lax`,
7 days. JavaScript cannot read it, and the frontend never stores a token. Call
the API with `fetch(url, { credentials: "include" })` and the browser sends the
cookie by itself. Logout works even when not logged in, so calling it twice is fine.
