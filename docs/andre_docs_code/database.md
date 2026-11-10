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
| `Friendship` / `friendships` | one row per pair of users + status `pending` / `accepted` / `declined` | no self-friendship; one row per pair, whichever side asked |
| `Block` / `blocks` | one row per block: `blocker_id` blocked `blocked_id` | no self-block; one block per (blocker, blocked); Alice and Bob can each block the other |
| `Top10Comment` / `top10_comments` | a comment on someone's Top 10 (`top10_owner_id`, `author_id`) | not blank; owners may comment on their own (to reply) |
| `Top10Reaction` / `top10_reactions` | a `like` or `dislike` on someone's Top 10 | one per person per Top 10; not on your own |
| `UserSession` / `sessions` | one row per logged-in browser: SHA-256 of the cookie token + expiry | token hash unique; expiry required |

Not enforced by the database, so **your code must check these**:
- Who can see a Top 10: `is_top10_public = False` means friends only.
- Max comment length.

Songs added by hand use `provider="manual"` and a generated uuid as `provider_id`.

## Friend requests

The HTTP API is in [`social.md`](social.md). Behind it, the route module
`backend/app/routes/v1/friendships.py` holds one rule function per action. Call
these from other backend code; never change `friendships` or `blocks` rows
yourself:

```python
from app.routes.v1.friendships import NotAllowed, NotFound, send_request

try:
    friendship = send_request(session, me, them)
    session.commit()
except NotFound:
    ...  # 404: unknown user, nothing to act on, or they blocked me
except NotAllowed:
    ...  # 409: a rule refuses
```

| Rule function | Does | Returns |
|---|---|---|
| `send_request(session, me, them)` | ask them | the `Friendship` row |
| `accept_request(session, me, them)` | accept their pending request | the `Friendship` row |
| `decline_request(session, me, them)` | decline their pending request; the row stays | `None` |
| `cancel_request(session, me, them)` | withdraw my pending request; deletes the row | `None` |
| `remove_friend(session, me, them)` | end an accepted friendship; deletes the row | `None` |
| `block_user(session, me, them)` | block them; deletes any friendship row | `None` |
| `unblock_user(session, me, them)` | lift my block | `None` |

None of them commits. The caller commits once the rule returned.

What `send_request` does with the pair's existing row:

| Existing row for the pair | Result |
|---|---|
| none | new row, `pending` |
| they asked me, `pending` | becomes `accepted` |
| I already asked, `pending` | unchanged, same row returned |
| `accepted` | unchanged |
| `declined`, they said no to me | `NotAllowed` |
| `declined`, I said no to them | reopens as `pending`, with me as requester |
| I blocked them | `NotAllowed("unblock first")` |
| they blocked me | `NotFound` |
| (a user id that does not exist, or a deleted account) | `NotFound` |

Every rule refuses a deleted account with `NotFound`. All rules except
`block_user` and `unblock_user` also check blocks the same way as
`send_request`. If both users ask at the same instant, the second request finds
the first one's row and the rules above apply (asking back accepts).

## Checking and listing friends

Read-only queries are in `backend/app/crud/friendship.py`. None of them flushes
or commits. Never write the "both directions" query yourself:

```python
from app.crud.friendship import are_friends, is_blocked, list_friends, list_pending

are_friends(session, me, them)   # True only when the pair's row is accepted
is_blocked(session, me, them)    # True when either user blocked the other
list_friends(session, me)        # list[User], accepted friends, ordered by id
list_pending(session, me)        # (users who asked me, users I asked), each ordered by id
```

- `are_friends` and `is_blocked` give the same answer whichever user goes first.
- `list_friends` and `list_pending` leave out soft-deleted accounts
  (`deleted_at` set). Need only the ids? `[friend.id for friend in list_friends(session, me)]`.

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
`test_friendships.py`, `test_blocks.py`, `test_comments_reactions.py`,
`test_user_sessions.py`.
