import { api } from './api.ts'

export type SongSearch = {
  q: string
  artist: string
  album: string
  provider: string
  sort: 'title' | 'artist' | 'created_at'
  order: 'asc' | 'desc'
  page: number
  page_size: number
}

export type CatalogSong = {
  id: number
  title: string
  artist: string
  album: string | null
  provider: string
  cover_url: string | null
  duration_ms: number | null
  created_at: string
}

export type SongSearchResponse = {
  items: CatalogSong[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export const initialSearch: SongSearch = {
  q: '', artist: '', album: '', provider: '',
  sort: 'title', order: 'asc', page: 1, page_size: 20,
}

export function searchSongs(search: SongSearch, signal: AbortSignal) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(search)) {
    if (value !== '') params.set(key, String(value))
  }
  return api<SongSearchResponse>(`/api/v1/search/songs?${params}`, { signal })
}
