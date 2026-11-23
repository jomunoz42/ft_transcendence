# Advanced song search — issue #56

Search is available from the **Search** sidebar link or `/search` after signing in.
It queries songs already saved in PostgreSQL and works without Spotify credentials
or network access to Spotify. It does not import songs or modify playlists.

## Run and demonstrate

Start the application using the repository's normal setup (`make up`; on a fresh
database, `make migrate`). No new migration is required for this feature.
Use an existing account or register one in the app.

The offline demonstration seed is optional. To add its records explicitly:

```bash
docker compose exec -T backend python -m app.seed_search
```

Use `docker-compose` instead if your installation uses Compose v1. Alternatively,
with backend dependencies installed and `DATABASE_URL` configured, run
`python -m app.seed_search` from `backend/`.

The seed inserts 60 fictional manual songs with provider IDs
`search-demo-v1-000` through `search-demo-v1-059`. It never updates or deletes
existing rows, creates accounts, or changes Top 10 entries. Repeating it inserts
zero rows once all IDs exist. It is not invoked by startup or migrations. Any
pre-existing row with one of these provider IDs is preserved, even if edited.

Demonstration with the unmodified seed:

1. Open **Search**, enter `Demo Track` in the search box, and click **Search**.
   At 20 results per page, the 60 demo songs span three pages.
2. Set **Artist** to `Demo Ensemble` and search: 40 songs span two pages.
3. Also set **Album** to `Demo Sessions` and **Provider** to `manual`, then search:
   30 songs still span two pages. Use Next and Previous to inspect both pages.
4. Change **Sort by** between Title, Artist, and Date added; try both directions.
   Equal values use the song ID to give a repeatable order. Sorting returns to page 1.
5. Change **Results per page** to 10: the same filtered results span three pages.
6. Try an unmatched artist to see the empty state, then use **Clear filters**.

Counts above describe the seed records; other matching catalog records can add
to them. Ten demo songs have no album or duration, and title/date pairs contain
ties to exercise sorting. All seeded songs are labeled `manual`; imported songs
retain their actual provider.

## API contract

`GET /api/v1/search/songs` requires a valid `myplaylist_session` cookie.
Missing, expired, revoked, or deleted-account sessions return 401.

| Parameter | Default | Rules |
| --- | --- | --- |
| `q` | Empty | Up to 200 characters; case-insensitive substring of title, artist, or album |
| `artist` | Empty | Up to 200 characters; case-insensitive artist substring |
| `album` | Empty | Up to 200 characters; case-insensitive album substring |
| `provider` | Empty | Up to 50 characters; exact, case-sensitive provider match |
| `sort` | `title` | `title`, `artist`, or `created_at` |
| `order` | `asc` | `asc` or `desc` |
| `page` | `1` | Integer, 1–10,000 |
| `page_size` | `20` | Integer, 1–100 |

Text is trimmed after length validation. Empty text omits that filter, allowing
catalog browsing. Filters combine with AND; `q` matches any of its three fields.
SQL wildcards such as `%` and `_` are treated as literal text. Album filters exclude
rows with no album. Unknown providers produce an empty result, not a validation
error. Invalid declared parameters return FastAPI's standard 422 response.
NUL bytes in any text search parameter also return 422 before a database query.

Example, using a previously obtained authenticated cookie jar:

```bash
curl -b .cookies --get http://localhost:8000/api/v1/search/songs \
  --data-urlencode 'artist=Demo Ensemble' \
  --data-urlencode 'album=Demo Sessions' \
  --data-urlencode 'provider=manual' \
  --data-urlencode 'sort=title' \
  --data-urlencode 'order=asc' \
  --data-urlencode 'page=2' \
  --data-urlencode 'page_size=20'
```

Use your configured HTTPS origin if applicable. The response is:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

Each item exposes only `id`, `title`, `artist`, `album`, `provider`, `cover_url`,
`duration_ms`, and `created_at`. It does not expose raw provider metadata or
playlist ownership. `total` counts the complete filtered result before slicing.
Valid pages past the end return empty `items` with the requested page and current
totals. Text sorting uses `lower(column)`; every sort appends `id` in the same
direction as a unique tie-breaker.

Pagination uses bounded LIMIT/OFFSET. Its ordering is stable for unchanged data;
concurrent inserts, deletes, or edits can move rows between pages. Counts and rows
are separate queries under the existing database isolation, so concurrent writes
can also change totals during a request. This API does not promise a frozen
cross-request snapshot. For catalogs larger than the page limit, refine filters.

The frontend applies text filters with **Search** (or Enter); sort, direction,
and page-size changes apply immediately to the last submitted filters. Each
change starts at page 1. Requests include session cookies; superseded requests
are aborted and their responses ignored. A 401 returns the user to login.

## Verification

Backend tests use real PostgreSQL and the existing transaction/savepoint fixtures.
Run them against a migrated test database configured by `DATABASE_URL`:

```bash
cd backend
pytest -q tests/test_song_search.py tests/test_search_seed.py
```

In Compose, with the backend service configured to use a test database:

```bash
docker compose exec -T backend pytest -q tests/test_song_search.py tests/test_search_seed.py
```

These tests cover authentication, filters, literal wildcard handling, all sort
directions and ties, multiple pages, totals, bounds, response fields, no Spotify
calls, compatibility of existing song routes, and seed idempotency/preservation.

The self-contained backend regression suite can be run with:

```bash
pytest -q --ignore=tests/test_backend.py
```

The existing `test_backend.py` is a separate legacy smoke suite requiring the
Victor/Luna sample accounts and a functioning Spotify integration. It makes
committed changes; do not point it at a database whose data you need to preserve.

Frontend checks (Node 22.12+ supported by the existing Vite toolchain):

```bash
cd frontend
npm ci
npm test
npm run typecheck
npm run build
```

Vitest and Testing Library cover request parameters, page resets, server ordering,
pagination, loading/empty/error/retry states, validation errors, expired sessions,
stale responses, and navigation through the authenticated app.

## Scope and existing limitations

The existing `/api/v1/songs`, `/api/v1/songs/search`, song-detail, and profile APIs
retain their contracts. Spotify search still uses its original endpoint. No
database migration, search extension, or production dependency is added.

Genre, release year, popularity, user search, and adding results to a Top 10 are
outside this feature. The existing Top 10 creation code still hardcodes a manual
provider ID, which can cause uniqueness failures when adding new songs. This
unrelated bug is unchanged; use the opt-in seed to demonstrate the local catalog.
