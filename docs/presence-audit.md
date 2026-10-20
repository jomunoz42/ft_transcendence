# Backend presence audit — issue #7

Audited on 2026-10-20 on `joao_presence_contract`, starting at `7d35973`
(merged PR #26, following PR #24). The acceptance criteria below come from
[issue #7](https://github.com/jomunoz42/ft_transcendence/issues/7).
The [frontend contract](presence-contract.md) is the handoff for Pedro's #27.

## Acceptance criteria

All six criteria are implemented at the backend boundary. Opening the
application makes a user online **when the frontend opens an authenticated
`/ws` connection**; an HTTP login or page load alone does not establish presence.
The React connection and display remain Pedro's work.

| Issue #7 criterion | Implementation and existing evidence |
| --- | --- |
| Opening the application makes an authenticated user online | `ConnectionManager.connect` registers the socket after authenticated acceptance and schedules online only for the first socket. `test_registration_schedules_online_before_snapshot_delivery`, `test_first_connection_per_user_goes_online_and_extra_tabs_do_not`. |
| Multiple connections for one user are handled correctly | Membership is a set per user; every ready recipient tab receives events. `test_send_to_user_reaches_every_target_tab_and_no_other_user`, `test_presence_event_reaches_only_accepted_friends_on_all_their_tabs`. |
| Closing one of several connections does not mark the user offline | `disconnect` removes only that socket and schedules no transition if another remains. `test_only_final_tab_disconnect_goes_offline_and_duplicates_are_harmless`, `test_presence_notifications_follow_first_and_last_tab_transitions`. |
| Closing the final connection produces an offline transition | Final removal schedules current state through the dispatcher; failed sends also remove dead sockets. `test_failed_send_on_final_tab_still_notifies_friends_offline`, `test_postgres_cookie_snapshot_friend_visibility_and_reconnect`. |
| Relevant clients receive presence updates in real time | `find_presence_recipients` uses accepted, non-deleted friends from `list_friends`; every outbound frame revalidates the recipient session. `test_only_accepted_friends_in_either_direction_are_recipients`, `test_presence_event_reaches_only_accepted_friends_on_all_their_tabs`, `test_deleted_friends_are_excluded_from_snapshots_and_delivery`. |
| Reconnect/disconnect cases are tested | Real PostgreSQL cookie reconnect test plus dispatcher ordering/coalescing tests: `test_reconnect_cannot_overtake_offline_already_being_sent`, `test_rapid_reconnect_before_dispatch_coalesces_to_current_state`, `test_state_change_during_snapshot_send_arrives_after_snapshot`. |

Test files: `backend/tests/test_connection_manager.py`, `test_websocket.py`,
`test_presence.py`, `test_presence_dispatcher.py`, `test_presence_resilience.py`,
`test_websocket_auth.py`, `test_websocket_postgres.py`, `test_realtime_lifecycle.py`,
and `test_realtime_config.py`.

## Lifecycle and failure review

- **Authentication:** cookie-only handshake; exact Origin allowlist; invalid,
  expired, revoked, and deleted-account sessions rejected. Protected frames
  require fresh session validation; idle validation runs every ten seconds.
- **Snapshots:** first application frame is a private `presence_snapshot`;
  subsequent `presence` events use numeric user IDs and boolean state. Both use
  one dispatcher, preventing an initial snapshot from overtaking a live update.
  A changed friendship set causes another replacement snapshot.
- **Logout:** successful commit triggers session-scoped removal immediately;
  independent logins survive. Existing tests cover failed commits, notification
  failures, pending initialization, and logout during outbound validation.
- **Database failures:** initial snapshot/authentication/revalidation fail closed;
  transient presence delivery lookups retry with bounded exponential backoff,
  retaining final offline state. Transient friendship refresh failures retry on
  the next tick. Non-transient delivery failures are logged and require repair
  and client reconnection. These behaviors have dedicated failure tests.
- **Disconnect/reconnect:** cleanup is idempotent; state assignments can repeat or
  coalesce. A fresh connection receives a new snapshot, with no durable replay.
  Abrupt network loss waits for transport detection. State is process-local, so
  deployment must use one backend worker.
- **Authorization timing:** friendships are selected from committed database
  state at lookup time, not transactionally locked through network delivery.
  A frame already authorized/in flight cannot be recalled by a concurrent
  friendship change or logout. Friendship snapshots refresh on a five-second
  schedule plus queue/lookup time; they are not an instantaneous removal signal.

## Changes needed

No backend functionality or missing acceptance-test gap was found. Existing
coverage already exercises every #7 criterion and the requested failure paths.
The changes are documentation only:

- Add `docs/presence-contract.md`: exact wire contract, browser authentication,
  endpoint URLs, client example, reconnect guidance, and two-account recipe.
- Add this audit with acceptance mapping and validation evidence.
- Link the contract from `docs/realtime.md`.
- Correct `backend/DEVELOPMENT.md`, whose old broadcast, handshake-only auth,
  and manual echo instructions contradicted PR #26.

No frontend files, authentication/friendship implementation, or infrastructure
configuration were changed.

## Validation

Executed on 2026-10-20 with Python 3.14.4 and the existing backend virtualenv:

| Check | Result |
| --- | --- |
| Focused realtime suite with `DATABASE_URL=sqlite:///:memory:` (nine files listed above) | **199 passed, 30 skipped**; skips are the PostgreSQL integration/lifecycle cases. |
| Alembic migrations on an isolated PostgreSQL 18.6 database | All six migrations applied successfully through `4ee1b8f18961`. |
| Complete backend suite, `.venv/bin/pytest -q`, PostgreSQL 18.6, database timezone UTC | **355 passed, 0 failed, 0 skipped**, in 8.37 seconds. |
| JavaScript example | Extracted from the contract and passed `node --check`. |
| Documentation review | Cited test functions verified to exist; `git diff --check` passed. |

The suite emits one existing Starlette/AnyIO `BlockingPortal` deprecation warning.
Docker was unavailable in this WSL environment, so PostgreSQL binaries and a
fresh cluster were placed under `/tmp`, using only a private Unix socket. No
project database or environment file was modified. The temporary server was
stopped after verification. Tests require execution outside the restricted
sandbox here: its asyncio thread-wakeup behavior caused timeouts in the first
attempt; the same focused suite then passed without code changes.

The first full run used the host-inherited `Europe/Lisbon` database timezone:
354 passed and the existing `test_a_new_session_expires_in_seven_days` failed.
This audit date's seven-day interval crosses the daylight-saving change, giving
169 elapsed hours instead of that test's expected 168. Setting **only the
temporary database** to UTC, matching the default container timezone, yielded
the clean full-suite result above. Non-UTC deployments should separately review
whether session duration means calendar days or exactly 168 hours; no unrelated
authentication change was made for this presence handoff.

The browser recipe is documented but was not executed in an interactive browser
in this environment. Automated tests exercise the ASGI application, real
PostgreSQL sessions, and committed HTTP logout; they do not verify browser TLS,
cookie policy, or Pedro's UI.

**Readiness:** the backend contract is ready for Pedro's #27 under the existing
single-worker architecture. The contract makes the local HTTPS/API-origin setup
and temporary friend-roster setup explicit so the UI can be implemented without
guessing backend messages or adding a friendship route.
