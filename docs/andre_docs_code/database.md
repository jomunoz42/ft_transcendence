# André's code docs — Database

PostgreSQL 17, accessed with SQLAlchemy 2.x, schema managed by Alembic. The code
lives in `backend/app/db/`. For why it is built this way, see [`whys.md`](whys.md).
To run it locally, see [`database/DEVELOPMENT.md`](../../database/DEVELOPMENT.md).

## Getting a session

Routes get a database session from the `get_session` FastAPI dependency. One
session is opened per request and always closed. **It does not commit for you.**

```python
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import User

@router.get("/users/{user_id}")
def read_user(user_id: int, session: Session = Depends(get_session)):
    return session.get(User, user_id)

# writing: add, then commit yourself
session.add(user)
session.commit()
```

## Tables

All models are in `backend/app/db/models.py`. Every rule listed here is enforced by
Postgres, so breaking one raises `IntegrityError`. Deleting a user deletes
everything that belongs to them.

| Model / table | What it holds | Rules |
|---|---|---|
| `User` / `users` | login data: email, password hash, lockout, soft-delete (`deleted_at`) | email unique and lowercase |
| `Profile` / `profiles` | one per user: display name, avatar, bio, `is_top10_public`, online status | one profile per user |
| `Song` / `songs` | one row per track, shared by everyone | `(provider, provider_id)` unique, so a track is stored once |
| `Top10Entry` / `top10_entries` | a user's ranked list, one row per (user, song, rank) | rank 1–10; one song per rank; no song twice; a song in someone's Top 10 cannot be deleted |
| `Friendship` / `friendships` | one row per pair of users + status `pending` / `accepted` / `declined` / `blocked` | no self-friendship; one row per pair, whichever side asked |
| `Top10Comment` / `top10_comments` | a comment on someone's Top 10 (`top10_owner_id`, `author_id`) | not blank; owners may comment on their own (to reply) |
| `Top10Reaction` / `top10_reactions` | a `like` or `dislike` on someone's Top 10 | one per person per Top 10; not on your own |
| `UserSession` / `sessions` | one row per logged-in browser: SHA-256 of the cookie token + expiry | token hash unique; expiry required |

Not enforced by the database, so **your code must check these**:
- Who can see a Top 10: `is_top10_public = False` means friends only.
- Max comment length.

Songs added by hand use `provider="manual"` and a generated uuid as `provider_id`.

## Friend requests

Never insert into `friendships` directly. Call `send_friend_request` instead:

```python
from app.db.friendships import send_friend_request, FriendRequestNotAllowed

try:
    friendship = send_friend_request(session, requester_id=me, addressee_id=them)
    session.commit()
except FriendRequestNotAllowed:
    ...  # return a 403/409 to the client
```

| Existing row for the pair | Result |
|---|---|
| none | new row, `pending` |
| they asked me, `pending` | becomes `accepted` |
| I already asked, `pending` | unchanged, same row returned |
| `accepted` | unchanged |
| `declined`, they said no to me | `FriendRequestNotAllowed` |
| `declined`, I said no to them | reopens as `pending`, with me as requester |
| `blocked` | `FriendRequestNotAllowed`, whoever asks |
| (asking yourself, or a user id that does not exist) | `FriendRequestNotAllowed` |

If both users ask at the same instant, the second request finds the first one's
row and is handled by the rules above (asking back accepts). The caller never
sees an `IntegrityError`, and the session keeps working after any refusal.

## Checking and listing friends

Never write the "both directions" query yourself. Use these two read-only
helpers; neither flushes nor commits:

```python
from app.db.friendships import are_friends, list_friends

are_friends(session, me, them)   # True only when the pair's row is accepted
list_friends(session, me)        # list[User], accepted friends, ordered by id
```

- `are_friends` gives the same answer whichever user goes first. No row,
  `pending`, `declined` and `blocked` all give `False`.
- `list_friends` leaves out soft-deleted accounts (`deleted_at` set). Need only
  the ids? `[friend.id for friend in list_friends(session, me)]`.

## Changing the schema

1. Edit or add models in `backend/app/db/models.py`.
2. Generate a migration (stack running):
   `docker-compose run --rm backend alembic revision --autogenerate -m "short_name"`
3. **Read the generated file** in `backend/alembic/versions/`, and fix anything it got wrong.
4. Apply it: `make migrate`.

Never edit a migration that is already applied. Add a new one instead.

## Commands

| Command | Does |
|---|---|
| `make up` | start the stack |
| `make migrate` | apply outstanding migrations |
| `make test` | run the backend tests (real Postgres) |
| `make down` | stop the stack, **keeps the data** |
| `make db-reset` | **DESTRUCTIVE**: wipes the database; run `make migrate` after |

Tests for each table are in `backend/tests/`: `test_user_profile.py`, `test_top10.py`,
`test_friendships.py`, `test_friend_requests.py`, `test_comments_reactions.py`,
`test_user_sessions.py`.
