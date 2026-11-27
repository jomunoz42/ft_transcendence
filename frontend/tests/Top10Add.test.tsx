import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import HomePage from '../src/pages/HomePage.tsx'
import type { ProfileData } from '../src/lib/api.ts'
import type { SpotifySong } from '../src/lib/top10Api.ts'

const spotifySong: SpotifySong = {
  provider_id: 'spotify-track-1',
  title: 'Night Drive',
  artist: 'Test Artist',
  album: 'City Lights',
  cover_url: 'https://images.example/night-drive.jpg',
  duration_ms: 185_000,
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function entry(id: number, rank: number) {
  return {
    id,
    rank,
    song_id: id,
    song: {
      title: `Existing song ${id}`,
      artist: 'Existing artist',
    },
  }
}

function mockTop10Server(
  initialProfile: ProfileData,
  addResponse: Response = json({ id: 2, rank: 2, song_id: 2 }),
) {
  let profileRequests = 0
  let added = false

  const fetch = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')

    if (url.pathname === '/api/v1/profiles/me') {
      profileRequests += 1

      if (added) {
        return json({
          ...initialProfile,
          top10_entries: [
            ...(initialProfile.top10_entries ?? []),
            {
              id: 2,
              rank: 2,
              song_id: 2,
              song: spotifySong,
            },
          ],
        })
      }

      return json(initialProfile)
    }

    if (url.pathname === '/api/v1/songs/search') {
      return json([spotifySong])
    }

    if (url.pathname === '/api/v1/profiles/7/top10') {
      added = addResponse.ok
      return addResponse.clone()
    }

    throw new Error(`Unexpected URL: ${url}`)
  })

  vi.stubGlobal('fetch', fetch)

  return {
    fetch,
    profileRequestCount: () => profileRequests,
  }
}

function renderHome() {
  return render(
    <HomePage
      user={{ id: 7, display_name: 'Listener' }}
      presenceStatus="ready"
    />,
  )
}

describe('adding a song to the Top 10', () => {
  it('searches Spotify and adds the selected song to the first available rank', async () => {
    const server = mockTop10Server({
      display_name: 'Listener',
      top10_entries: [entry(1, 1), entry(3, 3)],
    })
    const user = userEvent.setup()

    renderHome()

    await user.click(await screen.findByRole('button', { name: /Add a song to your list/ }))
    await user.type(screen.getByLabelText('Song or artist'), '  A/B & more  ')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    const addButton = await screen.findByRole('button', {
      name: 'Add Night Drive by Test Artist to your Top 10',
    })
    const searchCall = server.fetch.mock.calls.find(([input]) => {
      return String(input).includes('/api/v1/songs/search')
    })
    const searchUrl = new URL(String(searchCall?.[0]), 'http://localhost')

    expect(searchUrl.searchParams.get('q')).toBe('A/B & more')

    await user.click(addButton)

    const addCall = server.fetch.mock.calls.find(([input]) => {
      return String(input).includes('/api/v1/profiles/7/top10')
    })
    const init = addCall?.[1]

    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('include')
    expect(JSON.parse(String(init?.body))).toEqual({
      song: {
        provider_id: 'spotify-track-1',
        title: 'Night Drive',
        artist: 'Test Artist',
        album: 'City Lights',
        cover_url: 'https://images.example/night-drive.jpg',
        duration_ms: 185_000,
      },
      rank: 2,
    })
    expect(await screen.findByText('Night Drive')).toBeTruthy()
    expect(screen.getByText('Night Drive was added to your Top 10.')).toBeTruthy()
    expect(server.profileRequestCount()).toBe(2)
  })

  it('does not search with an empty query', async () => {
    const server = mockTop10Server({
      display_name: 'Listener',
      top10_entries: [],
    })
    const user = userEvent.setup()

    renderHome()

    await user.click(await screen.findByRole('button', { name: /Add a song to your list/ }))
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(screen.getByRole('alert').textContent).toContain('Enter a song or artist')
    expect(server.fetch).toHaveBeenCalledTimes(1)
  })

  it('keeps the picker open and shows an add conflict', async () => {
    const server = mockTop10Server(
      { display_name: 'Listener', top10_entries: [] },
      json({ detail: 'This song is already in your Top 10' }, 409),
    )
    const user = userEvent.setup()

    renderHome()

    await user.click(await screen.findByRole('button', { name: /Add a song to your list/ }))
    await user.type(screen.getByLabelText('Song or artist'), 'Night Drive')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.click(await screen.findByRole('button', {
      name: 'Add Night Drive by Test Artist to your Top 10',
    }))

    await waitFor(() => {
      expect(screen.getByText('This song is already in your Top 10')).toBeTruthy()
    })
    expect(screen.getByLabelText('Song or artist')).toBeTruthy()
    expect(server.profileRequestCount()).toBe(1)
  })

  it('does not offer another song when all ten ranks are occupied', async () => {
    mockTop10Server({
      display_name: 'Listener',
      top10_entries: Array.from({ length: 10 }, (_, index) => {
        return entry(index + 1, index + 1)
      }),
    })

    renderHome()

    await screen.findByText('Existing song 10')
    expect(screen.queryByRole('button', { name: /Add a song to your list/ })).toBeNull()
  })
})
