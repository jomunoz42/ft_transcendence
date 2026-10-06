# André's code docs — Why's

Why André's database and auth code is built the way it is. How to *use* the
code is in [`database.md`](database.md) and [`auth.md`](auth.md). Got a question
that is not here? Ask André, and the answer gets added.

**Database**
- [Why SQLAlchemy + Alembic, and what does each do?](#why-sqlalchemy--alembic-and-what-does-each-do)
- [Why one migration file per change?](#why-one-migration-file-per-change)
- [Why does DB code live in `backend/app/db/` and not `database/`?](#why-does-db-code-live-in-backendappdb-and-not-database)
- [Why do friend requests work this way?](#why-do-friend-requests-work-this-way)
- [Why bigint ids, and not unsigned or UUID?](#why-bigint-ids-and-not-unsigned-or-uuid)
- [Why are rules enforced by Postgres and not only in Python?](#why-are-rules-enforced-by-postgres-and-not-only-in-python)

**Auth**
- [Why Argon2 for passwords?](#why-argon2-for-passwords)
- [Why SHA-256 for session tokens, if passwords use Argon2?](#why-sha-256-for-session-tokens-if-passwords-use-argon2)
- [Why does `verify_password` return `False` instead of raising?](#why-does-verify_password-return-false-instead-of-raising)

---

## Database

### Why SQLAlchemy + Alembic, and what does each do?

They are two different tools that are easy to mix up:

| | SQLAlchemy | Alembic |
|---|---|---|
| Is | the ORM | the migration tool |
| Deals with | rows and data | table structure (`CREATE`/`ALTER TABLE`) |
| Runs | on every request | once per schema change |

SQLAlchemy is the standard Python route, and Alembic comes from the same authors.
The team switched from Prisma (TypeScript-first) before any code depended on it.

Things that trip people up:
- `--autogenerate` diffs the models against the database. It misses renames
  and some constraint changes, so **read every generated file** before applying it.
- A model Alembic cannot import is invisible to it. New models go in
  `backend/app/db/models.py`.
- The connection string comes from `DATABASE_URL` in `.env`, never from
  `alembic.ini`, so credentials stay out of git.

### Why one migration file per change?

Each file is one step of schema history, like a commit. The database stores the
last step it applied (table `alembic_version`), and `alembic upgrade head` runs
only the steps after it. If you edit an already-applied file, every existing
database skips your change.

**New change = new file. Never edit an applied one.** Files are named after what
they do (`friendships.py`), from the `-m` you pass to `alembic revision`.

### Why does DB code live in `backend/app/db/` and not `database/`?

The running app has to import the models and sessions, so they must sit inside the
Python package. `database/` holds what is not imported: the dev guide and the
`db-check.sh` script.

### Why do friend requests work this way?

The rules are in [`database.md`](database.md#friend-requests). The reasons:
- **Asking back accepts.** Two pending rows would leave both people waiting, and
  every "are A and B friends?" query would have to check both directions.
- **Only the person who said no can reopen.** That person can change their mind,
  but nobody can spam requests after being declined. Reopening goes back to
  `pending`, so the other person still has to say yes.
- **Blocked refuses both sides.** Unblocking will be its own action.

### Why bigint ids, and not unsigned or UUID?

Postgres has no unsigned integers, and an autoincrement id never goes negative
anyway. Bigint is simple and fast. If ids ever become public-facing (in URLs),
switching to UUID is cheap while there is no real data.

### Why are rules enforced by Postgres and not only in Python?

With constraints in the database (unique, check, foreign keys), a bug in any route
cannot store bad data. The insert fails with `IntegrityError` instead. Only rules
that depend on *who is asking* live in code: who can see a Top 10 is decided by
routes, and max comment length is decided by the endpoint.

---

## Auth

### Why Argon2 for passwords?

- **Hashed and salted:** the subject requires it. A leaked database leaks no
  passwords, and two users with the same password get different hashes.
- **Slow on purpose.** A login barely notices, but an attacker trying billions of
  guesses is slowed enormously. Fast hashes like SHA-256 are the wrong tool here.
- **Over bcrypt.** Argon2 won the Password Hashing Competition and is OWASP's first
  recommendation. bcrypt is older and weaker against GPUs.

### Why SHA-256 for session tokens, if passwords use Argon2?

| | Password | Session token |
|---|---|---|
| Chosen by | a human | the server, 32 random bytes |
| Guessable? | yes | no |
| Hashed with | Argon2 (slow, salted) | SHA-256 (fast, unsalted) |

- Slowness only protects guessable secrets, and a random token has nothing to guess.
- The token must be searchable. Each request hashes the cookie and finds it with
  one indexed query. Argon2's random salt would make that impossible.
- It runs on every request: Argon2 costs ~50–100 ms, SHA-256 costs microseconds.

The token is still hashed, so a leaked `sessions` table cannot be used to log in.

### Why does `verify_password` return `False` instead of raising?

The library raises on a wrong password *and* on a corrupt stored hash. Returning
`False` keeps login code a plain `if not verify_password(...)`, and a corrupt row
means "login failed" instead of a 500 error.
