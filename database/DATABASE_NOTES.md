# Notes — why the database layer looks like this

Answers to questions asked while building the database layer, kept so they do not
have to be re-derived. Newest at the top. `DEVELOPMENT.md` covers how to run
things; this file covers why they are the way they are.

---

## What does each part of the database do?

Eight tables, all defined in `backend/app/db/models.py` and created by the
migrations in `backend/alembic/versions/` (full design: `database/db-schema.md`).
Every rule below is enforced by Postgres itself, so a bug in the backend cannot
store bad data — the insert fails with `IntegrityError` instead.

**Users and profiles** — `users_and_profiles.py`, ticket 03

- `users`: login data (email, password hash, lockout, soft-delete). Email is unique.
- `profiles`: one per user — display name, avatar, bio, and `is_top10_public`
  (false = friends only). Deleting a user deletes their profile.

**Songs and the Top 10** — `songs_and_top10.py`, ticket 04

- `songs`: one row per track, shared by everyone. `provider` says where it came
  from (`spotify`, `deezer`, `manual`) and `(provider, provider_id)` is unique, so
  the same track is never stored twice.
- `top10_entries`: a user's ranked list — one row per (user, song, rank).
  - rank must be 1–10
  - one song per rank per user
  - no song twice in the same Top 10
  - a song still in someone's Top 10 cannot be deleted
  - deleting a user deletes their Top 10

**Friendships** — `friendships.py`, ticket 05

- `friendships`: one row per pair of users — who asked, who was asked, and the
  status (`pending`, `accepted`, `declined`, `blocked`).
  - nobody can befriend themself
  - only one row per pair, whichever side asked first
  - status must be one of the four values
  - deleting either user deletes the friendship
- Requests go through `send_friend_request` — see the next entry for its rules.

**Comments and reactions** — `comments_and_reactions.py`, ticket 06

- `top10_comments`: text left on someone's Top 10. Blank comments are rejected.
  Owners can comment on their own Top 10 (to reply).
- `top10_reactions`: a like or dislike on someone's Top 10.
  - only `like` or `dislike`
  - one reaction per person per Top 10 (changing it updates the same row)
  - nobody can react to their own Top 10, so self-likes cannot inflate rankings
- Both tables point at two users: the Top 10's owner and the author. Deleting
  either one deletes the row.

**Sessions** — `sessions.py`, auth ticket 02

- `sessions`: one row per logged-in browser — the server-side half of the login
  cookie. The browser holds the raw token; this table holds only its SHA-256
  hash, the user, and when it expires.
  - each token hash is unique
  - every session has an expiry
  - deleting a user deletes their sessions
- The model is `UserSession`, so it does not clash with SQLAlchemy's `Session`.

**Not enforced by the database, on purpose**

- Who can *see* a Top 10 (`is_top10_public`): depends on who is looking, so the
  route layer decides.
- Max comment length: a product choice, validated by the endpoint.

Tests for each part: `backend/tests/test_user_profile.py`, `test_top10.py`,
`test_friendships.py`, `test_friend_requests.py`, `test_comments_reactions.py`,
`test_user_sessions.py`.

---

## What are the rules for sending a friend request?

A pair of users has at most one row in `friendships` (the unordered-pair unique
index), so a request never blindly inserts. `send_friend_request` in
`backend/app/db/friendships.py` looks up the pair's row and decides from its state:

| Existing row for the pair | What happens |
|---|---|
| none | new row, `pending` |
| the other person asked me, `pending` | `accepted` — both asked, so they are friends |
| I already asked, `pending` | nothing, same row returned |
| `accepted` | nothing, already friends |
| `declined`, and I am the one who was declined | refused (`FriendRequestNotAllowed`) |
| `declined`, and I am the one who said no | same row reopens as `pending`, with me as requester |
| `blocked` | refused, whichever side asks |

Why these rules:

- **Asking back accepts.** Two pending rows would leave both people waiting on each
  other, and every "are A and B friends?" query would need to check both directions.
- **Only the person who said no can reopen.** Stops someone spamming a request after
  being turned down, but lets the one who declined change their mind. When they do,
  the other person still has to say yes — it goes back to `pending`, not `accepted`.
- **Blocked refuses both sides.** Unblocking will be its own action, not a side
  effect of a friend request.

Not handled: both users clicking at the same instant. Both see no row, and the
second insert hits the unique index (`IntegrityError`) — so a duplicate row is
impossible, but the second click gets an error. The endpoint can retry once it
exists; marked with a `ponytail:` comment in the code.

Decided by André, 2026-09-21. Tests: `backend/tests/test_friend_requests.py`.

---

## Why one Alembic file per migration instead of a single file?

Each file is one step of schema history, like a commit. Postgres records the last
step it applied in the `alembic_version` table, and `alembic upgrade head` runs only
the steps after it. Folding ticket 04 into the first migration would break every
database already at step one: Alembic would see it as up to date and never create
`songs` or `top10_entries`. New change, new file — never edit an applied one.

Filenames are only labels. Alembic chains migrations by the `revision` /
`down_revision` ids inside each file, so the files were renamed from the default
`<hex id>_<slug>.py` to just what they do (`users_and_profiles.py`,
`songs_and_top10.py`), set by `file_template = %%(slug)s` in `backend/alembic.ini`.
Each file's docstring says what it creates and which migration it runs after. The
hex ids stay inside the files: changing them would orphan the value already stored
in `alembic_version`. Name new migrations with a short `-m`, e.g.
`alembic revision --autogenerate -m "friendships"` gives `friendships.py`.

---

## Why is there no Postgres Dockerfile, and is the container defined in `.env.example`?

No — the container is defined in `docker-compose.yml`, service `postgres`, with
`image: postgres:17-alpine`. `.env.example` only holds the variables that service
reads (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`); the
official image's entrypoint uses them to create the user and database on first start.

A Dockerfile is a recipe for building a custom image. The backend has one because it
is our own code. Postgres is not: the official image already does everything needed,
so compose pulls it as-is. A Dockerfile would only earn its place for extensions, a
custom locale, or baked-in config. Init SQL does not need one — mount it into
`/docker-entrypoint-initdb.d/` instead.

---

## Why not just run `down -v` every session while there is no real data yet?

Tempting, and the data genuinely is disposable right now. Rejected anyway, for
reasons that are not about the data:

- Every `up` would then start empty, so `alembic upgrade head` becomes mandatory
  before anything works — `alembic_version` lives in the volume too.
- `make db-check` and ticket 03's last checkbox exist to prove data survives
  `down`/`up`. Making `-v` the default stops exercising the property they test.
- It saves 48 MB of disk and no RAM at all.
- Worst of it: "we will stop using `-v` once the data matters" is a rule that has to
  fire on exactly the session where it is easiest to forget, and the failure is
  silent and unrecoverable. No error, no prompt, the rows are simply gone.

The clean-database benefit is real though — it catches migrations that only work
against an already-dirty local database. So it was split out instead of defaulted:

- `make down` — the automatic session-end rule, keeps the volume.
- `make db-reset` — DESTRUCTIVE, deliberate, drops the volume and starts empty.
- `make migrate` — reapplies the schema afterwards.

Destruction is now always something typed on purpose, with nothing to remember to
turn off later.

## Should `down` also remove the volumes, to stop Docker using resources?

No. A volume is disk storage, not a process — it uses zero CPU and zero RAM whether
or not anything is running. `docker-compose down` already stops and removes the
containers, which is what actually frees resources. Adding `-v` deletes the
`postgres_data` volume and every row in the database while freeing nothing but disk
(measured at 48 MB when the schema was fresh).

What keeps running after `down` is the Docker daemon itself — `dockerd` plus
`containerd`, measured at about 184 MB resident on this machine, independent of any
container. No compose flag affects that. To free it, run `wsl --shutdown` from
Windows, which stops the daemon and the WSL VM. The volume survives on disk; it is
just files.

So there are three levels, and only the first belongs to the agent:

1. `make down` — stops the containers. Runs at the end of every session in this repo.
2. `wsl --shutdown` from Windows — frees the daemon and the VM. André's call.
3. `down -v` — deletes the database. Never, unless the data is genuinely disposable.

## Is Alembic the ORM? Does it mean no more SQL?

No on both counts, and the two tools are easy to merge by mistake.

**SQLAlchemy is the ORM.** It is what removes SQL from everyday data work:
`session.add(User(email=...))`, `select(User).where(User.email == ...)`. It maps rows
to Python objects and back.

**Alembic only manages schema structure over time** — `CREATE TABLE`, `ALTER TABLE`,
`DROP COLUMN`. It never touches application data at runtime. Separate package, same
authors, built on top of SQLAlchemy.

| | SQLAlchemy | Alembic |
| --- | --- | --- |
| Deals with | rows and data | table structure |
| When it runs | every request | once per schema change |
| Here | `session.execute(...)`, the models | making `users` and `profiles` exist |

Drop Alembic and the ORM still works — but tables get created by hand-written
`CREATE TABLE`, and every teammate has to run the same statements in the same order.

SQL does not disappear entirely either way. `/health` already runs `text("SELECT 1")`
because a raw ping is simpler than an ORM query, and migrations occasionally need
`op.execute("...")` for what autogenerate cannot express.

## What is Alembic, and why is it laid out this way?

Alembic is the migration tool for SQLAlchemy. The models describe what the tables
*should* look like; Alembic records how to get there from whatever the database
currently is. Each change is a numbered Python file with `upgrade()` and
`downgrade()`, committed to git, and the revisions form a chain so any database can
be walked forward with one command.

- `alembic revision --autogenerate -m "..."` diffs the models against the live
  database and writes the migration file.
- `alembic upgrade head` applies everything outstanding.
- A table named `alembic_version` inside the database stores the revision it is on.
  That is how Alembic knows what still needs applying.

For this project the revision chain is the schema history: ticket 03 creates `users`
and `profiles`, 04 adds `songs` and `top10_entries` on top of it, 05 `friendships`,
06 the comment and reaction tables. A teammate cloning the repo runs
`alembic upgrade head` once and lands on the same schema.

`--autogenerate` is a diff, not an oracle: it reliably catches new tables and
columns, but misses or mangles renames and some constraint changes. Read every
generated file before applying it.

Layout choices:

- **`backend/alembic/` and `backend/alembic.ini`, the tool's defaults.** `alembic.ini`
  has to sit in the directory the command runs from, and every tutorial and future
  teammate expects these paths.
- **`alembic.ini` has an empty `sqlalchemy.url`.** The generated default hardcodes a
  connection string into a committed file. Instead `alembic/env.py` sets it from the
  `DATABASE_URL` environment variable, so real credentials never reach git.
- **`env.py` imports `Base` from `app.db.models`.** Autogenerate can only see models
  that are imported, so anything not reachable from that import is silently invisible
  to migrations.
- **`alembic/versions/` is committed, not ignored.** The migrations are source code —
  they are how a teammate's database ends up matching yours.

## Why are the ports written `"${POSTGRES_PORT:-5432}:5432"`?

Four things stacked in one line:

- **`HOST:CONTAINER`.** Left is the port on your machine, right is the port inside
  the container. Postgres always listens on 5432 inside its own container, so the
  right side is hardcoded — it has no reason to change.
- **`${POSTGRES_PORT:-5432}`** is a shell-style default: read `POSTGRES_PORT` from
  `.env`, and if it is unset or empty, use 5432. If something already occupies 5432
  on your machine (another Postgres, another 42 project), set `POSTGRES_PORT=5433`
  in `.env` and the compose file does not change.
- **The quotes are not decorative.** YAML 1.1 parses an unquoted `5432:5432` as a
  base-60 number rather than a string. Quoting avoids it.
- **`ports:` is for the host, not for the backend.** Containers on a compose network
  reach each other by service name, so the backend connects to `postgres:5432` over
  the internal network whether or not anything is published. The published port only
  exists so `psql` or a GUI can reach the database from outside.

Open improvement: `ports` binds `0.0.0.0` by default, so the database is reachable
from the local network. `"127.0.0.1:${POSTGRES_PORT:-5432}:5432"` would restrict it
to the host, which is what a dev database wants.

## Why `$${POSTGRES_USER}` with two dollar signs in the healthcheck?

`$$` escapes compose's own variable interpolation, so a single `$` survives into the
container and *its* shell expands the variable from `env_file`. With one `$`, compose
would substitute it at parse time on the host, where the variable is not set, and the
healthcheck would run with an empty user.

## Why does `docker-compose.yml` still declare `version: "3.9"`?

Compose v2 treats `version` as obsolete and ignores it. Only `docker-compose` v1.29.2
is installed on this machine, and v1 needs the key to read the v3 file format. The
Makefile and `db-check.sh` both detect which binary exists, so either works.

## Why is `backend/` bind-mounted into its container?

`volumes: - ./backend:/app` means code edits and test runs do not need an image
rebuild — otherwise every change to a test requires `docker-compose build backend`,
because the source is copied in at build time. This is a development convenience and
should not ship to production as-is, where the image should be self-contained.

## Why does database code live in `backend/app/db/` and not in `database/`?

Alembic and SQLAlchemy have to be importable by the running app, so the models and
session code must sit inside the Python package. `database/` holds what does not need
importing: the schema design, the runnable check, and documentation. The `db/` package
exists so the ownership boundary is visible in the repository, not just agreed in
conversation.

## Why did Docker say `permission denied ... /var/run/docker.sock`?

The Docker daemon runs as root and its socket is owned `root:docker` with mode `660`,
so only root and members of the `docker` group can open it. Fixed with
`sudo usermod -aG docker $USER`, where `-a` appends — without it, `-G` would replace
every other group, including `sudo`. Group membership is stamped on a process at
login, so WSL needed a full `wsl --shutdown`, not just a new shell.

Worth knowing: the `docker` group is effectively root. A member can mount the host
filesystem into a container and write anywhere, with no password. Standard on a dev
machine, wrong on a shared or production one. Reversible with
`sudo gpasswd -d $USER docker`.
