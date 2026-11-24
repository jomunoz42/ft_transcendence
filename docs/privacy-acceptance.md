# Issue #57 acceptance evidence

Verified on 24 November 2026 against the isolated `issue57_gdpr_audit` branch.
The fetched `origin/main` was `3803b95`; the branch was already based on it.
No pending PR was merged. PR #65 (42 OAuth) was still open.

## Subject and issue criteria

The 42 subject in `docs/subject.md` §IV.8 and issue #57 require a user data
request, confirmed data deletion, a readable data export, confirmation emails
for data operations, and authorization preventing cross-user access or erasure.

| Criterion | Evidence |
| --- | --- |
| Request data | Signed-in users can use Settings to call `POST /api/v1/privacy/export`; anonymous requests return 401. |
| Readable export | The endpoint returns a versioned, indented JSON attachment with `Cache-Control: no-store`. The live download contained the requester's account, profile, shared Top 10 song, friendship, authored comment, reaction, and received notification. Explicit allowlists excluded hashes, credentials, raw notification text and keys, and another user's private content. |
| Confirmed deletion | A live request delivered a short-lived token by Mailpit. The server rejected another user's token and a missing `DELETE` confirmation; the valid signed token removed the account and sessions. Replay returned 401. Shared songs and the other user remained. |
| Confirmation emails | Mailpit received the export confirmation, deletion challenge, and best-effort completion email. Tests also cover delivery failures. An export remains downloadable after confirmation-email failure; deletion cannot proceed if challenge delivery fails. |
| Cross-user authorization | Database-backed sessions scope all three privacy routes. Automated tests and the live flow confirmed anonymous rejection, requester-only export, cross-user token rejection, and immediate rejection of a deleted session. |

## Verification performed

- Alembic reported exactly one head, `7c9e2b63d4a1`. On disposable PostgreSQL,
  `upgrade head`, `check`, `downgrade -1`, `upgrade head`, and `current` passed.
  `check` reported no model/schema drift.
- Complete backend suite on a newly created tmpfs PostgreSQL database with the
  legacy module's minimal Victor/Luna seed: **675 passed, 2 failed**, one
  existing Starlette deprecation warning. Both failures are in unchanged
  `tests/test_backend.py`: its repeated Top 10 insert triggers an uncaught
  uniqueness error, and its Spotify search call lacks `SPOTIFY_CLIENT_ID`.
  The first unseeded run had 49 failures in that module because Luna was absent;
  those were fixture setup failures, not GDPR regressions. No xfails were added.
- New PostgreSQL concurrency tests passed: only one of two simultaneous
  challenges is issued; only one of two confirmations for a token succeeds;
  reciprocal notifications do not deadlock simultaneous account deletions.
- Frontend: **51 tests passed**, typecheck passed, production build passed.
  Lint passed with one pre-existing `useNotifications.ts:39` warning.
- A live run used the actual backend, a disposable PostgreSQL container, and
  Mailpit on an isolated Docker network. It passed registration, authenticated
  JSON attachment inspection, export email, challenge email, cooldown,
  cross-user rejection, explicit confirmation, completion email, deleted-session
  rejection, notification anonymization, and shared-data preservation. The
  verifier printed no email body or token. No persistent database volume was
  mounted and no existing container was changed.

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
   readable JSON with `format_version: 2`, and its account email belongs to
   Alice. Check that no password hash, session token, raw notification key, or
   Bob private text appears. Mailpit should show an export confirmation for
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
   authored social records must be absent.

## Remaining limitations and follow-ups

- Browser automation was unavailable for this run; the steps above are the
  remaining visual and multi-profile browser acceptance check.
- OAuth-only deletion must be exercised after PR #65 merges. The current
  deletion flow uses a session and email token, not a password.
- Accounts soft-deleted under earlier versions are not automatically erased.
  Inventory and remediate them in a separate, reviewed operation; do not run
  that operation as part of this feature.
- The production SMTP provider and sender remain deployment configuration.
  The app supports STARTTLS or SSL; Mailpit's insecure transport is restricted
  to local development.
