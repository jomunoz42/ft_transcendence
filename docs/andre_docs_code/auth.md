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

## Sessions

The `sessions` table exists (see [`database.md`](database.md#tables)). The
functions to create, check and end sessions are coming.
