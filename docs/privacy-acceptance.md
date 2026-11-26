# Issue #57 acceptance evidence

Revalidated on 26 November 2026 in an isolated local branch rebased onto
`origin/main` at `e281ed9` (including PR #77's Message model and PR #79's
Caddy limit). PR #78 was not in that main revision. The backend comparison
used its direct predecessor `d249e14`, whose backend tree is identical.
The earlier Mailpit live flow below was performed on 24 November. Real-browser
acceptance against the rebased branch was completed on 26 November as described
below.

## Subject and issue criteria

The 42 subject in `docs/subject.md` §IV.8 and issue #57 require a user data
request, confirmed data deletion, a readable data export, confirmation emails
for data operations, and authorization preventing cross-user access or erasure.

| Criterion | Evidence |
| --- | --- |
| Request data | Chromium used Settings to download `myplaylist-data.json`; an anonymous API request returned 401. |
| Readable export | Chromium saved and parsed version 3 JSON with `Cache-Control: no-store`. The file contained Alice's account, updated profile, shared Top 10, friendship, authored comment, reaction, received notification, and four messages sent or received once each. Three unrelated messages, credentials, session token, raw notification text/key, and deletion token were absent. |
| Confirmed deletion | Chromium requested a challenge, showed that the account remained active, rejected an invalid token, and required `DELETE` before submitting the valid token. It then redirected to login. PostgreSQL showed Alice's user, profile, sessions, challenge, and messages in both directions removed while unrelated messages and a shared song remained. |
| Confirmation emails | A disposable local SMTP catcher received Alice's export, challenge, and completion emails. With the catcher stopped, Chromium still downloaded Bob's export and displayed the email failure state. A controlled 503 response showed the download error state without starting a download. |
| Cross-user authorization | Direct API requests rejected Bob using Alice's token (400), an expired challenge (400), a replay after deletion (401), and anonymous export (401). Alice's second browser session lost access after deletion. |

## Browser and end-to-end acceptance, 26 November 2026

Docker Desktop had no running daemon, so the Compose stack, Caddy and its HTTPS
configuration were unavailable. The acceptance setup used the actual GDPR
frontend and backend, a fresh `gdpr_accept` database in disposable PostgreSQL
18.6, a local SMTP capture service, and Vite's self-signed HTTPS proxy. It did
not touch the existing Compose stack or persistent volumes. Headless Chromium
159.0.8154.6 opened `https://127.0.0.1:15443`; Vite proxied the API to
`127.0.0.1:18000`. The disposable SMTP service listened on `127.0.0.1:11025`.
The browser accepted only the temporary self-signed certificate for this run.

### Browser-validated behavior

- Registered and signed in Alice through the frontend, followed the Settings
  navigation link, edited her display name and biography, and saw the save
  confirmation. The privacy section described the exported and deleted
  messages after the copy correction in this branch.
- Downloaded and parsed the JSON attachment through the real download action.
  It matched Alice's account and seeded data. All four Alice-participant
  messages appeared once with exactly `id`, `sender_id`, `recipient_id`, `body`,
  and `created_at`; three conversations without Alice were absent. A second
  download after challenge issuance excluded the raw token and its hash.
- Saw the successful download notice and the deletion request's expiry and
  cooldown UI. Requesting and cancelling deletion left Alice signed in. An
  invalid token showed an error; reopening the existing-token form worked.
  The permanent-delete button stayed disabled until a token and the exact
  `DELETE` phrase were present. The valid emailed token completed deletion
  and redirected to login without putting the token in the URL.
- Reloaded Alice's second browser session and saw the login page. A fresh
  login attempt with Alice's old credentials received 401 and stayed on login.
- The approved deletion flow uses an emailed token entered in Settings with
  explicit `DELETE` confirmation. It intentionally has no clickable link.
- With SMTP stopped, Bob's export still downloaded as valid JSON and the UI
  reported the failed confirmation email. A controlled 503 response to the
  export request showed an error and started no download; this 503 check
  exercised the frontend response path, not a failing backend request.

### Direct API and database validation

- Anonymous export returned 401. The old `DELETE /api/v1/settings` returned
  405 without deleting Alice; `GET` and `POST` on settings returned 200.
- The SMTP catcher received Alice's export confirmation, deletion challenge,
  and completion email. The challenge was not in the request response. Bob
  could not use Alice's token (400). A separate disposable account's challenge
  was expired in the test database, then rejected (400). Alice's deleted
  session and token replay returned 401.
- PostgreSQL confirmed zero Alice user, profile, session, deletion-request,
  and sent/received message rows after confirmation. The three unrelated
  message IDs, Bob's Top 10 entry, and their shared song remained.

### Checks not completed in this environment

- Full Docker Compose, Caddy HTTPS, PostgreSQL 17, and production SMTP
  delivery were not exercised. PostgreSQL 17 was unavailable in the host
  package repository; 18.6 was used for the native acceptance stack.
- The expired-token API check advanced the disposable database row's expiry;
  it did not wait 15 real minutes. Automated regression tests cover the
  token's embedded expiry. WebSocket closure was not part of this native
  browser run; the default origin allowlist excludes the temporary Vite port.

The browser harness initially raced the profile load, and a subsequent reset
was launched from the wrong directory. Both harness issues were corrected and
the final run completed on a freshly migrated, empty acceptance database.
Neither was an application defect. The only application edit found during
acceptance was outdated Settings copy that omitted messages; it is corrected.

## Automated regression baseline

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

## Optional manual repeat on the Compose stack

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

- The native Chromium acceptance above passed. The steps above remain useful
  for a later Compose, Caddy, PostgreSQL 17 and Mailpit verification.
- Avatar export is deferred until PR #75's schema lands.
- OAuth-only deletion must be exercised after PR #65 merges. The current
  deletion flow uses a session and email token, not a password.
- Accounts soft-deleted under earlier versions are not automatically erased.
  Inventory and remediate them in a separate, reviewed operation; do not run
  that operation as part of this feature.
- The production SMTP provider and sender remain deployment configuration.
  The app supports STARTTLS or SSL; Mailpit's insecure transport is restricted
  to local development.
