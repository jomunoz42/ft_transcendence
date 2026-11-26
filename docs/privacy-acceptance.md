# Issue #57 acceptance evidence

Revalidated on 26 November 2026 in an isolated local branch rebased onto
`origin/main` at `e281ed9` (including PR #77's Message model and PR #79's
Caddy limit). PR #78 was not in that main revision. The backend comparison
used its direct predecessor `d249e14`, whose backend tree is identical.
The earlier Mailpit live flow below was performed on
24 November; browser acceptance still needs to be repeated after this rebase.

## Subject and issue criteria

The 42 subject in `docs/subject.md` §IV.8 and issue #57 require a user data
request, confirmed data deletion, a readable data export, confirmation emails
for data operations, and authorization preventing cross-user access or erasure.

| Criterion | Evidence |
| --- | --- |
| Request data | Signed-in users can use Settings to call `POST /api/v1/privacy/export`; anonymous requests return 401. |
| Readable export | The endpoint returns a versioned, indented JSON attachment with `Cache-Control: no-store`. The export includes messages sent and received by the requester once each, with explicit fields. Tests exclude unrelated conversations, hashes, credentials, raw notification text and keys, and another user's private content. |
| Confirmed deletion | A live request delivered a short-lived token by Mailpit. The server rejected another user's token and a missing `DELETE` confirmation; the valid signed token removed the account and sessions. Replay returned 401. PostgreSQL tests now also verify that messages in both directions disappear while unrelated conversations remain. |
| Confirmation emails | Mailpit received the export confirmation, deletion challenge, and best-effort completion email. Tests also cover delivery failures. An export remains downloadable after confirmation-email failure; deletion cannot proceed if challenge delivery fails. |
| Cross-user authorization | Database-backed sessions scope all three privacy routes. Automated tests and the live flow confirmed anonymous rejection, requester-only export, cross-user token rejection, and immediate rejection of a deleted session. |

## Verification performed

- Latest main's Alembic head was `c85ea1da6073`; the privacy migration now
  follows it. Alembic reported one branch head, `7c9e2b63d4a1`. On isolated
  PostgreSQL 18.6, `upgrade head`, `check`, `downgrade -1`, `upgrade head`, and
  `current` passed. `check` found no model/schema drift. PostgreSQL 17 was not
  available in this host's package repository.
- Focused GDPR, authentication, settings, message, notification, and session
  tests: **231 passed, 15 known xfailed**. New tests cover both message
  directions, recipient scoping, exact fields, once-only inclusion, and
  deletion cascades with unrelated conversations retained.
- Complete GDPR branch suite with minimal Victor/Luna fixture seed:
  **826 passed, 15 known xfailed, 1 failed**. A separate latest-main run on
  the same PostgreSQL instance and Python environment had **794 passed,
  15 known xfailed, 1 failed**. The identical failure is the legacy
  `tests/test_backend.py::test_backend_authorized[req21-exp21]`, which requires
  an unset `SPOTIFY_CLIENT_ID`. Both runs reported one Starlette deprecation
  warning. No xfails were added.
- PostgreSQL concurrency tests passed: only one of two simultaneous challenges
  is issued; only one of two confirmations for a token succeeds; reciprocal
  notifications do not deadlock simultaneous account deletions.
- Frontend: **51 tests passed**; typecheck, lint, and production build passed.
  Lint reported one existing `useNotifications.ts:39` warning.
- On 24 November, a live run used the actual backend, a disposable PostgreSQL
  container, and Mailpit on an isolated Docker network. It passed registration,
  authenticated JSON attachment inspection, export email, challenge email,
  cooldown, cross-user rejection, explicit confirmation, completion email,
  deleted-session rejection, notification anonymization, and shared-data
  preservation. That earlier run did not cover messages.

## João's browser acceptance steps

Use an isolated development deployment with a disposable database. Configure
the Mailpit Compose override, a unique random `PRIVACY_TOKEN_SECRET` of at least
32 bytes, and the usual application settings. Open the application through its
HTTPS address and Mailpit at `http://127.0.0.1:8025`. Use throwaway accounts.

1. Register Alice and Bob. Sign in as Alice in one browser profile and again in
   a second independent browser profile. Sign in as Bob in a third profile.
   For the shared-data check, add the same available song to both Top 10 lists;
   make the accounts friends and add an Alice-authored comment on Bob's list.
   If the local song catalog is empty, use the opt-in demo seed described in
   `docs/advanced-search.md` on this disposable deployment.
2. As Alice, open **Settings → Privacy and account** and select **Download my
   data**. Confirm that the browser saves `myplaylist-data.json`, the file is
   readable JSON with `format_version: 3`, and its account email belongs to
   Alice. The `messages` array should contain any messages Alice sent or
   received, each once, with `id`, `sender_id`, `recipient_id`, `body`, and
   `created_at`. It should exclude conversations between other accounts.
   Check that no password hash, session token, or raw notification key appears.
   Mailpit should show an export confirmation for
   Alice. The download should work even if that email cannot be delivered.
3. Select **Email me a deletion token**. Confirm that Settings shows the
   15-minute expiry and five-minute request cooldown. Mailpit should show the
   challenge email. Check that the token never appears in the address bar.
4. Select **Cancel**, refresh Settings, then select **I already have a token**.
   Alice must still be signed in. The emailed token remains valid until expiry
   or replacement; cancelling the form alone does not erase the account.
5. As Bob, open Settings, select **I already have a token**, paste Alice's token,
   type `DELETE`, and submit. The request must fail, and Bob must remain signed
   in. Do not capture the token in screenshots or shared logs.
6. Return to Alice. An invalid token must show an error. With the valid token,
   the permanent-delete button must stay disabled until the exact word
   `DELETE` is entered. Submit once. Alice should be redirected to login; the
   current WebSocket should close and Alice's blocked-user browser cache should
   be removed. Refreshing a protected URL should not show account content.
7. Refresh Alice's second browser profile. Its previously valid session must
   now be rejected. Mailpit should show a completion email. Bob should still
   sign in and see any shared song that was on both lists. Alice's account and
   authored social records and messages sent or received by Alice must be
   absent; unrelated conversations must remain.

## Remaining limitations and follow-ups

- Browser automation was unavailable for this run; the steps above are the
  remaining visual and multi-profile browser acceptance check.
- Avatar export is deferred until PR #75's schema lands.
- OAuth-only deletion must be exercised after PR #65 merges. The current
  deletion flow uses a session and email token, not a password.
- Accounts soft-deleted under earlier versions are not automatically erased.
  Inventory and remediate them in a separate, reviewed operation; do not run
  that operation as part of this feature.
- The production SMTP provider and sender remain deployment configuration.
  The app supports STARTTLS or SSL; Mailpit's insecure transport is restricted
  to local development.
