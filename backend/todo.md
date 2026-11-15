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

## Phase 3 — Advanced features

9. Advanced search (module: 1pt)
   - [ ] Search profiles by music tastes
   - [ ] Song Advanced search GET /api/v1/search/songs?q=...&filter=...&page=...
   - [ ] Implement pagination, sorting, filtering across endpoints
   - [ ] Add song manually
[maybe handled by Joao] 10. Notifications API (module: 1pt)
   - [ ] GET /api/v1/notifications — list notifications
   - [ ] PUT /api/v1/notifications/{id}/read — mark as read
   - [ ] Backend creates notifications on: friend request, comment, reaction, etc.
11. GDPR compliance (module: 1pt)
    - [ ] GET /api/v1/users/me/data-export — export all user data as JSON
    - [x] DELETE /api/v1/settings — soft-delete account
12. [x] Input validation everywhere — both Pydantic (request) and DB constraints
13. [ ] HTTPS setup — coordinate with Person 4 (likely nginx reverse proxy with self-signed cert)

## Phase 4 — Polish

14. [x] Error handling middleware — consistent error response format across all routes
15. [ ] Rate limiting — if claiming the public API module
16. [ ] Metrics endpoint — /metrics for Prometheus scraping (coordinate with Person 4)
17. [x] API documentation — FastAPI generates this automatically at /docs and /redoc
