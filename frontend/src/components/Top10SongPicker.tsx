import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from 'react'

import { getErrorMessage } from '../lib/api.ts'
import { durationLabel } from '../lib/format.ts'
import {
  searchSpotifySongs,
  type SpotifySong,
} from '../lib/top10Api.ts'

type Top10SongPickerProps = {
  adding: boolean
  onSelect: (song: SpotifySong) => Promise<void>
}

export default function Top10SongPicker({
  adding,
  onSelect,
}: Top10SongPickerProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SpotifySong[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const searchRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    return () => {
      searchRequest.current?.abort()
    }
  }, [])

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const searchQuery = query.trim()

    if (!searchQuery) {
      setError('Enter a song or artist to search Spotify.')
      return
    }

    searchRequest.current?.abort()

    const request = new AbortController()
    searchRequest.current = request
    setSearching(true)
    setResults(null)
    setError('')

    try {
      const songs = await searchSpotifySongs(searchQuery, request.signal)

      if (!request.signal.aborted) {
        setResults(songs)
      }
    } catch (reason) {
      if (!request.signal.aborted) {
        setError(getErrorMessage(reason, 'Could not search Spotify.'))
      }
    } finally {
      if (!request.signal.aborted) {
        setSearching(false)
        searchRequest.current = null
      }
    }
  }

  function renderResults() {
    if (searching) {
      return <p className="social-state" role="status">Searching Spotify…</p>
    }

    if (results === null) {
      return null
    }

    if (results.length === 0) {
      return <p className="social-state">No songs found.</p>
    }

    return (
      <ul
        className="top10-search-results"
        aria-label="Spotify search results"
      >
        {results.map((song) => (
          <li key={song.provider_id} className="top10-search-result">
            {song.cover_url ? (
              <img src={song.cover_url} alt="" />
            ) : (
              <span className="top10-search-cover" aria-hidden="true">♫</span>
            )}

            <span className="top10-search-song">
              <strong>{song.title}</strong>
              <small>
                {song.artist}
                {song.album ? ` · ${song.album}` : ''}
              </small>
            </span>

            <span className="duration">
              {durationLabel(song.duration_ms)}
            </span>

            <button
              className="button button-outline"
              type="button"
              disabled={adding}
              aria-label={`Add ${song.title} by ${song.artist} to your Top 10`}
              onClick={() => {
                void onSelect(song)
              }}
            >
              {adding ? 'Adding…' : 'Add'}
            </button>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className="top10-picker" aria-busy={searching || adding}>
      <p className="top10-picker-hint">
        Search Spotify and choose one song to add to the first available rank.
      </p>

      <form className="top10-search-form" onSubmit={search}>
        <label htmlFor="top10-song-search">Song or artist</label>
        <div>
          <input
            id="top10-song-search"
            type="search"
            maxLength={200}
            value={query}
            disabled={searching || adding}
            onChange={(event) => {
              setQuery(event.target.value)
            }}
          />

          <button
            className="button button-dark"
            disabled={searching || adding}
          >
            {searching ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}
      {renderResults()}
    </div>
  )
}
