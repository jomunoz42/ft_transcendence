# Backend To-Do

## Phase 1 — Foundation

1. Set up the API structure/router organization
   - [x] Create route files (auth.py, profiles.py, friendships.py, settings.py in `app/routes/v1/`)
   - [x] Register them in main.py with `app.include_router()`
   - [x] URL conventions (`/api/v1/...`)
2. Define Pydantic schemas
   - [x] Request/response models for each domain (inline in each module)
3. Implement auth endpoints
   - [x] POST /api/v1/auth/register — email + password, hash with Argon2, create user + profile
   - [x] POST /api/v1/auth/login — verify credentials, return session cookie
   - [x] POST /api/v1/auth/logout — invalidate session
   - [x] Auth dependency (`current_user`) that protects all other routes
   - [x] argon2-cffi in requirements.txt
4. Implement core CRUD routes
   - [x] GET/POST /api/v1/profiles/me — view/edit own profile
   - [x] GET /api/v1/profiles/{user_id} — view someone's profile
   - [ ] Manage own Top 10 (via profile update endpoint)
   - [x] View someone's Top 10 (via profile endpoint, respecting visibility/friendship)

## Phase 2 — Social features

5. Friend system API
   - [x] POST /api/v1/friends/request/{user_id} — send request
   - [x] POST /api/v1/friends/accept/{user_id} — accept
   - [x] POST /api/v1/friends/decline/{user_id} — decline
   - [x] POST /api/v1/friends/cancel/{user_id} — cancel own request
   - [x] DELETE /api/v1/friends/{user_id} — unfriend
   - [x] GET /api/v1/friends — list friends
   - [x] GET /api/v1/friends/requests — pending requests
   - [x] POST /api/v1/friends/block/{user_id} — block
   - [x] POST /api/v1/friends/unblock/{user_id} — unblock
6. Comments & reactions API
   - [x] POST/GET /api/v1/profiles/{user_id}/comments
   - [x] POST/DELETE /api/v1/profiles/{user_id}/comments/{comment_id}
   - [x] POST/GET/DELETE /api/v1/profiles/{user_id}/reactions
7. Song search API
   - [x] GET /api/v1/songs/search?q=... — search by title/artist
   - [x] Integration with external music API (Spotify/Deezer)
8. Profile search API
   - [ ] GET /api/v1/profiles/search?q=... — search by username/display name

## Phase 3 — Bugs & PR fixes

9. Fix top10 UniqueViolation
   - [ ] Extract top10 logic out of `update_profile`
   - [ ] Delete old entries before inserting new ones (avoid unique constraint on `user_id, rank`)
   - [ ] Decide return behavior: 200 replace or 400 reject on re-post
10. Security fixes (from PR review)
    - [x] POST /api/v1/settings — return `_me(user)` not raw User (was leaking password_hash)
    - [x] POST /api/v1/profiles/me — return `_me_profile(profile)` not raw Profile
    - [x] Centralized error handling (`app/errors/__init__.py`)
    - [x] Removed broad `try/except` blocks hiding DB errors
    - [x] Explicit `session.commit()` in routes, removed yield-based `commit_session`
    - [x] `.env.example` — replaced real Spotify credentials with placeholders

## Phase 4 — Modules (my scope)

11. Standard User Management module (2pts Major)
    - [x] Users can update their profile information
    - [ ] Avatar upload — POST /api/v1/profiles/me/avatar (accept file, store, serve)
    - [ ] Default avatar for users who don't upload one
    - [x] Users can add friends and see online status
    - [x] Profile page displaying user information
12. Public API module (2pts Major)
    - [ ] API key model + generation endpoint
    - [ ] API key auth middleware (separate from session auth)
    - [ ] Rate limiting middleware
    - [ ] Add at least one PUT endpoint (currently only GET/POST/DELETE)
    - [x] Swagger docs — already free from FastAPI at /docs and /redoc

## Phase 5 — Mandatory requirements

13. Privacy Policy & Terms of Service
    - [ ] Backend endpoints to serve content
    - [ ] Coordinate with frontend for accessible pages (footer links)
    - [ ] Content must be relevant, not placeholder
14. HTTPS setup
    - [ ] TLS termination (nginx reverse proxy with self-signed cert or similar)
    - [ ] All browser-to-backend connections over HTTPS
15. Backend input validation audit
    - [ ] Audit all POST endpoints for proper Pydantic validation (types, lengths, formats)
    - [ ] Especially: registration, profile update, comments, reactions

## Phase 6 — Advanced features (stretch)

16. Advanced search (module: 1pt)
    - [ ] Song Advanced search GET /api/v1/search/songs?q=...&filter=...&page=...
    - [ ] Implement pagination, sorting, filtering across endpoints
    - [ ] Add song manually
17. GDPR compliance (module: 1pt)
    - [ ] GET /api/v1/users/me/data-export — export all user data as JSON
    - [x] DELETE /api/v1/settings — soft-delete account

## Not on me (tracked for awareness)

- OAuth 42 login — teammate
- Prometheus + Grafana monitoring — Joao
- WebSocket / chat / presence — teammate
- Friendships logic — Andre
- Notifications API — maybe Joao
- Frontend (CSS framework, UI, client-side validation)
