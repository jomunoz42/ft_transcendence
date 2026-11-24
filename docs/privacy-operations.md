# Account data operations

## Data export

`POST /api/v1/privacy/export` requires an authenticated session. It returns a
versioned, indented UTF-8 JSON attachment containing the account, profile,
ranked Top 10, friendships, outgoing blocks, authored comments and reactions,
and received notifications. The response is marked `Cache-Control: no-store`.
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
