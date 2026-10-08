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
- Email is stripped and lowercased before it is stored, so `A@x.com` and `a@x.com`
  are the same account. Password must be 8–128 characters and is never stripped.
  Display name is stripped and cannot be blank.
- After `EmailTaken` or `InvalidRegistration`, nothing was written and the session
  is still usable.
- A soft-deleted user's email stays taken. Freeing it (by anonymizing the email on
  GDPR delete) is decided for later, not built.

## Sessions

The `sessions` table exists (see [`database.md`](database.md#tables)). The
functions to create, check and end sessions are coming.
