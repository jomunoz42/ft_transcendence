# André's code docs — Social

How to call the friends API from the frontend. The rules behind it are in
[`database.md`](database.md#friend-requests), and the reasons are in
[`whys.md`](whys.md#why-do-friend-requests-work-this-way).

## HTTP routes — `/api/v1/friends`

Every route needs a login. Without the session cookie, the answer is 401.
`{id}` is always the *other* user's id. "Me" always comes from the cookie.

| Route | Does | Success |
|---|---|---|
| `GET` (no trailing slash) | my friends | 200 `[{"id", "display_name"}]` |
| `GET /requests` | pending requests | 200 `{"incoming": [...], "outgoing": [...]}` |
| `POST /request/{id}` | ask them to be friends | 200 `{"status": "pending"}`, or `"accepted"` |
| `POST /accept/{id}` | accept the request they sent me | 200 `{"status": "accepted"}` |
| `POST /decline/{id}` | decline the request they sent me | 200 `{"status": "declined"}` |
| `POST /cancel/{id}` | withdraw the request I sent them | 200 `{"status": "cancelled"}` |
| `DELETE /{id}` | stop being friends | 200 `{"status": "removed"}` |
| `POST /block/{id}` | block them | 200 `{"status": "blocked"}` |
| `POST /unblock/{id}` | lift my block | 200 `{"status": "unblocked"}` |

In `GET /requests`, `incoming` lists the users who asked me and `outgoing` the
users I asked. Each entry is `{"id", "display_name"}`. Both lists are ordered by
id, and deleted accounts never show up.

`POST /request/{id}` answers `"accepted"` when they had already asked me, so
asking back makes us friends straight away. Asking someone I am already friends
with also answers `"accepted"`, and asking again while my request waits answers
`"pending"`. Nothing changes in either case.

## Errors

Errors use FastAPI's `{"detail": ...}`.

| Code | When | `detail` |
|---|---|---|
| 401 | not logged in | `"Not logged in"` |
| 422 | `{id}` is my own id | `"Cannot act on yourself"` |
| 404 | nothing to act on: unknown or deleted user, no such request, not friends, no block to lift | `"Not found"` |
| 409 | a rule refuses | `"unblock first"`, or `"declined; only the person who said no can ask again"` |

**Blocking is hidden from the blocked user.** If Alice blocks Bob, every action
Bob tries on Alice answers 404, exactly as if Alice did not exist. Never show
Bob that he is blocked. Alice herself gets 409 `"unblock first"` when she tries
to ask, accept, decline, cancel or remove Bob, so her UI can offer an unblock button.

Blocking removes any friendship or pending request between the two users.
Blocking twice is fine and answers `"blocked"` again. Unblocking makes them
strangers: either of them can send a new request.

Not available yet: a list of the users I blocked.
