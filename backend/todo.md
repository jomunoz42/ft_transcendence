Phase 1 — Foundation (do first)

1. Set up the API structure/router organization
- Create backend/app/routers/ with separate files: auth.py, users.py, profiles.py, top10.py, friends.py, songs.py, comments.py, reactions.py
- Register them in main.py with app.include_router()
- Decide on URL conventions (e.g., /api/v1/...)
2. Define Pydantic schemas
- Create backend/app/schemas/ with request/response models for each domain
- These are separate from SQLAlchemy models — they define the API contract
3. Implement auth endpoints (coordinate with Andre)
- POST /api/v1/auth/register — email + password, hash with Argon2, create user + profile
- POST /api/v1/auth/login — verify credentials, return JWT
- POST /api/v1/auth/logout — invalidate token (if using blocklist) or just client-side
- JWT middleware/dependency that protects all other routes
- Add python-jose[cryptography] and argon2-cffi to requirements.txt
4. Implement core CRUD routes
- GET/PUT /api/v1/users/me/profile — view/edit own profile
- GET /api/v1/users/{id}/profile — view someone's profile
- GET/POST/PUT/DELETE /api/v1/users/me/top10 — manage own Top 10
- GET /api/v1/users/{id}/top10 — view someone's Top 10 (respecting is_top10_public / friendship)

Phase 2 — Social features

5. Friend system API (Andre built the DB logic, you expose it)
- POST /api/v1/friends/request/{user_id} — send request
- POST /api/v1/friends/accept/{user_id} — accept
- POST /api/v1/friends/decline/{user_id} — decline
- DELETE /api/v1/friends/{user_id} — unfriend
- GET /api/v1/friends — list friends
- GET /api/v1/friends/requests — pending requests
6. Comments & reactions API
- POST/GET /api/v1/users/{id}/top10/comments
- POST/DELETE /api/v1/users/{id}/top10/reaction
7. Song search API
- GET /api/v1/songs/search?q=... — search by title/artist
- Integration with external music API (Spotify/Deezer) or manual entry

Phase 3 — Advanced features

8. Advanced search (module: 1pt)
- GET /api/v1/search/users?q=...&sort=...&page=...
- GET /api/v1/search/songs?q=...&filter=...&page=...
- Implement pagination, sorting, filtering across endpoints
9. Notifications API (module: 1pt)
- GET /api/v1/notifications — list notifications
- PUT /api/v1/notifications/{id}/read — mark as read
- Backend creates notifications on: friend request, comment, reaction, etc.
10. GDPR compliance (module: 1pt)
- GET /api/v1/users/me/data-export — export all user data as JSON
- DELETE /api/v1/users/me — soft-delete account (already designed in schema)
11. Input validation everywhere — both Pydantic (request) and DB constraints (already there)
12. HTTPS setup — coordinate with Person 4 (likely nginx reverse proxy with self-signed cert)

Phase 4 — Polish

13. Error handling middleware — consistent error response format across all routes
14. Rate limiting — if claiming the public API module
15. Metrics endpoint — /metrics for Prometheus scraping (coordinate with Person 4)
16. API documentation — FastAPI generates this automatically, but review and clean up