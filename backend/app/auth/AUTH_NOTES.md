# Notes — why authentication works the way it does

Answers to questions asked while building auth, kept so they do not have to be
re-derived. Newest at the top. The plan and tickets live in `.scratch/auth/`
(local only); this file is the shared explanation. Database-side notes are in
`database/DATABASE_NOTES.md`.

---

## Why does `verify_password` return `False` instead of raising?

`argon2-cffi`'s `verify()` never returns `False`. A wrong password raises
`VerifyMismatchError`; a stored hash that is not a valid Argon2 string raises
`InvalidHashError`. `backend/app/auth/passwords.py` catches both (plus the
`VerificationError` base class) and returns `False`, so:

- the login code is a plain `if not verify_password(...)`, with no library
  exceptions leaking into auth logic;
- a corrupt `password_hash` row means "login failed", not a 500 crash.

The salt needs no column: it lives inside the hash string
(`$argon2id$v=19$m=...,t=...,p=...$<salt>$<hash>`), which is why hashing the same
password twice gives two different strings that both verify.

Built in ticket 01 (2026-09-22); tests in `backend/tests/test_passwords.py`.

---

## What is Argon2, and why hash passwords with it?

A password is never stored. It is **hashed**: turned into scrambled text that
cannot be turned back into the password.

```
"hunter22"  ->  $argon2id$v=19$m=65536,t=3,p=4$Xk2...$9fQ...
```

At login the typed password is hashed the same way and compared with the stored
hash. So a leaked database does not leak anyone's password directly.

- **Salted.** A random value is mixed in every time, so two users with the same
  password get different hashes, and one cracked hash does not reveal everyone who
  shares that password. The 42 subject requires passwords to be hashed and salted.
- **Deliberately slow.** Argon2 costs time and memory on purpose: a login barely
  notices, but an attacker trying billions of guesses against a stolen database is
  slowed enormously. Plain SHA-256 is the wrong tool — it is built to be fast.
- **Why Argon2 over bcrypt.** Argon2 won the 2015 Password Hashing Competition and
  is OWASP's first recommendation. bcrypt is still acceptable, but older and weaker
  against GPU attacks.

In code it is the `argon2-cffi` library:

```python
from argon2 import PasswordHasher

ph = PasswordHasher()
stored = ph.hash("hunter22")      # the salt is generated and kept inside the hash
ph.verify(stored, "hunter22")     # True; a wrong password raises VerifyMismatchError
```

Planned in `.scratch/auth/issues/01-password-hashing.md` (2026-09-21).
