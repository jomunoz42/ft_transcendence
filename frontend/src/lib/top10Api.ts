import { api, type Top10Entry } from './api.ts'

export type SpotifySong = {
  provider_id: string
  title: string
  artist: string
  album?: string | null
  cover_url?: string | null
  duration_ms?: number | null
}

export function searchSpotifySongs(
  query: string,
  signal: AbortSignal,
) {
  const params = new URLSearchParams({ q: query })

  return api<SpotifySong[]>(
    `/api/v1/songs/search?${params}`,
    { signal },
  )
}

export function addTop10Entry(
  userId: number,
  song: SpotifySong,
  rank: number,
) {
  return api<Top10Entry>(
    `/api/v1/profiles/${userId}/top10`,
    {
      method: 'POST',
      body: JSON.stringify({
        song: {
          provider_id: song.provider_id,
          title: song.title,
          artist: song.artist,
          album: song.album ?? null,
          cover_url: song.cover_url ?? null,
          duration_ms: song.duration_ms ?? null,
        },
        rank,
      }),
    },
  )
}
