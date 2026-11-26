# Account data operations

## Data export

`POST /api/v1/privacy/export` requires an authenticated session. It returns a
versioned, indented UTF-8 JSON attachment containing the account, profile,
ranked Top 10, friendships, outgoing blocks, authored comments and reactions,
received notifications, messages sent or received by the requester, and
deletion-request timing when applicable. The current format version is 3.
Each message appears once with its ID, sender ID, recipient ID, body and
creation timestamp. The response is marked `Cache-Control: no-store`.
The export is generated in memory and is not saved on the server or sent by
email. Credential and session hashes, other users' private text, notification
event keys, and actor IDs are excluded. Notification descriptions use the
application's standardized text for each known event type.

The backend attempts to send a confirmation email to the account address.
`X-Confirmation-Email` is `sent` or `failed`. An SMTP failure is logged without
address, credentials, message content, or tokens; **it does not prevent the
user from downloading their data**. The confirmation email contains no export
data or download link.

SMTP is configured with `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`,
`SMTP_SECURITY` (`starttls` or `ssl`), `SMTP_TIMEOUT_SECONDS`, and optional
`SMTP_USERNAME`/`SMTP_PASSWORD`. The optional `docker-compose.mailpit.yml`
override uses local-only plain SMTP and exposes Mailpit's web UI on
`127.0.0.1:8025` for development.

## Confirmed account deletion

`POST /api/v1/privacy/deletion-request` requires a live session. It sends a
15-minute signed, purpose-bound token to the account's current email. The token
is bound to the user ID and an authenticated digest of that address. The latest
token hash is stored in `privacy_deletion_requests`; the raw token is never
stored. A user can request another email after a five-minute cooldown. The
signing secret must be a unique random value of at least 32 bytes; the example
placeholder is rejected at runtime. The endpoint returns `202` without the
token, or `503` without creating a usable request if SMTP delivery fails.
Tokens belong in the JSON request body, never
in a URL or server log.

Closing or cancelling the frontend form does not revoke an already emailed
token; it remains usable by the authenticated account until it expires or is
replaced. No deletion occurs without the separate confirmation request.

The `202` response includes `expires_at` and `cooldown_seconds` for the
settings interface. Expired challenge rows for other accounts are removed
opportunistically when a new request is made; the requesting account's row is
replaced. The token lifetime exceeds the cooldown, so cleanup
does not bypass rate limiting. Accounts soft-deleted before this flow are not
automatically hard-deleted; their remediation needs a separate review and plan.

`POST /api/v1/privacy/deletion-confirm` requires that same account's live
session and JSON `{ "token": "...", "confirmation": "DELETE" }`. A valid token
is single-use because the account and request row are deleted in one database
transaction. It first takes a transaction-scoped PostgreSQL advisory lock so
two users deleting at once cannot deadlock through reciprocal notifications.
The transaction then locks the account row, anonymizes any retained
notifications that name it as actor, and deletes the account. Existing FK
cascades remove its profile, Top 10, friendships, blocks, comments, reactions,
messages in either direction, sessions, notifications, and deletion request.
Shared songs, unrelated conversations, and unrelated users
remain. Comments and reactions on the deleted user's Top 10 also disappear
because that shared resource no longer exists. The old unconfirmed
`DELETE /api/v1/settings` route is removed.

After commit, the browser session cookie is cleared and a completion email is
attempted. Completion email failure is logged without personal data; deletion
still returns success. Existing WebSocket sessions become invalid when their
database-backed session checks run.

Authenticated REST actions check the database-backed session on every request,
including during the WebSocket revalidation interval.
