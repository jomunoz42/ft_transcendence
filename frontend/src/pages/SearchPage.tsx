import { useEffect, useState, type FormEvent } from 'react'

import { ApiError, getErrorMessage } from '../lib/api.ts'
import { durationLabel } from '../lib/format.ts'
import { initialSearch, searchSongs, type SongSearch, type SongSearchResponse } from '../lib/searchApi.ts'

type Props = { onSessionExpired: () => void }
const emptyFilters = { q: '', artist: '', album: '', provider: '' }

export default function SearchPage({ onSessionExpired }: Props) {
  const [draft, setDraft] = useState(emptyFilters)
  const [search, setSearch] = useState<SongSearch>(initialSearch)
  const [result, setResult] = useState<{
    search: SongSearch
    data?: SongSearchResponse
    error?: string
  } | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    searchSongs(search, controller.signal).then((data) => {
      if (!controller.signal.aborted) setResult({ search, data })
    }).catch((reason: unknown) => {
      if (controller.signal.aborted) return
      if (reason instanceof ApiError && reason.status === 401) {
        onSessionExpired()
        return
      }
      setResult({ search, error: getErrorMessage(reason, 'Could not search songs.') })
    })
    return () => controller.abort()
  }, [search, onSessionExpired])

  const currentResult = result?.search === search ? result : null
  const data = currentResult?.data
  const error = currentResult?.error
  const loading = currentResult === null
  const appliedFilters = [
    search.q && `Text: ${search.q}`,
    search.artist && `Artist: ${search.artist}`,
    search.album && `Album: ${search.album}`,
    search.provider && `Provider: ${search.provider}`,
  ].filter(Boolean).join(' · ')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSearch((current) => ({ ...current, page: 1,
      q: draft.q.trim(), artist: draft.artist.trim(),
      album: draft.album.trim(), provider: draft.provider.trim(),
    }))
  }

  function reset() {
    setDraft(emptyFilters)
    setSearch({ ...initialSearch })
  }

  return (
    <section className="card search-page" aria-labelledby="song-search-title">
      <h2 id="song-search-title">Search songs</h2>
      <p className="search-description">Explore songs saved in the MyPlaylist catalog.</p>
      <form onSubmit={submit} className="song-search-form" aria-label="Song search">
        <label className="search-query">
          Search title, artist or album
          <input type="search" maxLength={200} value={draft.q}
            onChange={(event) => setDraft({ ...draft, q: event.target.value })} />
        </label>
        <label>
          Artist
          <input maxLength={200} value={draft.artist}
            onChange={(event) => setDraft({ ...draft, artist: event.target.value })} />
        </label>
        <label>
          Album
          <input maxLength={200} value={draft.album}
            onChange={(event) => setDraft({ ...draft, album: event.target.value })} />
        </label>
        <label>
          Provider
          <input maxLength={50} placeholder="Any provider" list="song-providers" value={draft.provider}
            onChange={(event) => setDraft({ ...draft, provider: event.target.value })} />
          <datalist id="song-providers"><option value="manual" /><option value="spotify" /></datalist>
        </label>
        <div className="search-actions">
          <button className="button button-dark" type="submit">Search</button>
          <button className="button button-outline" type="button" onClick={reset}>Clear filters</button>
        </div>
      </form>

      <div className="search-controls">
        <label>
          Sort by
          <select value={search.sort} onChange={(event) => setSearch({ ...search,
            sort: event.target.value as SongSearch['sort'], page: 1 })}>
            <option value="title">Title</option>
            <option value="artist">Artist</option>
            <option value="created_at">Date added</option>
          </select>
        </label>
        <label>
          Direction
          <select value={search.order} onChange={(event) => setSearch({ ...search,
            order: event.target.value as SongSearch['order'], page: 1 })}>
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </label>
        <label>
          Results per page
          <select value={search.page_size} onChange={(event) => setSearch({ ...search,
            page_size: Number(event.target.value), page: 1 })}>
            {[10, 20, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
          </select>
        </label>
      </div>

      <div aria-busy={loading}>
        {loading && <p role="status">Loading songs…</p>}
        {error && <div role="alert">
          <p>{error}</p>
          <button className="button button-outline" type="button" onClick={() => setSearch({ ...search })}>Retry</button>
        </div>}
        {data && <>
          <p role="status" aria-live="polite" aria-atomic="true">
            <span>{data.total} {data.total === 1 ? 'song' : 'songs'} found</span>
            {data.total > 0 && <>
              {' · '}
              <span>{data.page <= data.total_pages
                ? `Page ${data.page} of ${data.total_pages}`
                : `Page ${data.page} is empty`}</span>
            </>}
          </p>
          <p className="search-applied-filters">
            <strong>Applied filters:</strong> {appliedFilters || 'None'}
          </p>
          {data.items.length === 0 ? <p>{data.total === 0
            ? 'No songs match. Try changing your search or filters.'
            : 'This page is empty. Return to a previous page or search again.'}</p> : (
            <ul className="search-results" aria-label="Search results">
              {data.items.map((song) => (
                <li key={song.id}>
                  <div className="search-song-info">
                    <strong>{song.title}</strong>
                    <span>{song.artist}</span>
                    <span>{song.album ?? 'Album unknown'}</span>
                  </div>
                  <div className="search-song-meta">
                    <span>{song.provider}</span>
                    <span>{durationLabel(song.duration_ms ?? undefined)}</span>
                    <span>Added <time dateTime={song.created_at}>{new Date(song.created_at).toLocaleDateString()}</time></span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>}
      </div>
      <nav className="search-pagination" aria-label="Search pagination">
        <button className="button button-outline" type="button" disabled={loading || !!error || search.page <= 1}
          onClick={() => setSearch({ ...search, page: search.page - 1 })}>Previous</button>
        <button className="button button-outline" type="button"
          disabled={!data || search.page >= data.total_pages || search.page >= 10_000}
          onClick={() => setSearch({ ...search, page: search.page + 1 })}>Next</button>
      </nav>
      {data && search.page === 10_000 && data.total_pages > 10_000 && <p>Refine your filters to see more results.</p>}
    </section>
  )
}
