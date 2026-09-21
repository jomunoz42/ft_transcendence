# Notes — why authentication works the way it does

Answers to questions asked while building auth, kept so they do not have to be
re-derived. Newest at the top. The plan and tickets live in `.scratch/auth/`
(local only); this file is the shared explanation. Database-side notes are in
`database/NOTES.md`.

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
