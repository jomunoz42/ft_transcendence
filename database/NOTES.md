# Notes — why the database layer looks like this

Answers to questions asked while building the database layer, kept so they do not
have to be re-derived. Newest at the top. `DEVELOPMENT.md` covers how to run
things; this file covers why they are the way they are.

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
