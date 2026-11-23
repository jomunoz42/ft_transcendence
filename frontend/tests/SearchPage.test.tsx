import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import App from '../src/app/App.tsx'
import SearchPage from '../src/pages/SearchPage.tsx'
import type { CatalogSong, SongSearchResponse } from '../src/lib/searchApi.ts'

vi.mock('../src/websocket/useWebSocket.ts', () => ({
  useWebSocket: () => ({ status: 'ready' }),
}))

function song(id: number, title = `Song ${id}`): CatalogSong {
  return { id, title, artist: 'Test Artist', album: null, provider: 'manual',
    duration_ms: null, cover_url: null, created_at: '2024-01-01T00:00:00Z' }
}

function result(overrides: Partial<SongSearchResponse> = {}): SongSearchResponse {
  return { items: [song(1)], page: 1, page_size: 20, total: 1, total_pages: 1, ...overrides }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function mockServer(respond: (params: URLSearchParams) => Response | Promise<Response> = () => json(result())) {
  const fetch = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    if (url.pathname === '/api/v1/auth/me') return Promise.resolve(json({ id: 1, display_name: 'Listener' }))
    if (url.pathname === '/api/v1/profiles/me') return Promise.resolve(json({ display_name: 'Listener', top10_entries: [] }))
    if (url.pathname !== '/api/v1/search/songs') throw new Error(`Unexpected URL: ${url}`)
    return Promise.resolve(respond(url.searchParams))
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

function lastParams(fetch: ReturnType<typeof mockServer>) {
  return new URL(String(fetch.mock.calls.at(-1)?.[0]), 'http://localhost').searchParams
}

function button(name: string) {
  return screen.getByRole<HTMLButtonElement>('button', { name })
}

function multiPage(params: URLSearchParams) {
  const page = Number(params.get('page'))
  const size = Number(params.get('page_size'))
  return json(result({ items: [song(page, `Result page ${page}`)], page, page_size: size,
    total: 21, total_pages: Math.ceil(21 / size) }))
}

describe('song search', () => {
  it('loads the authenticated catalog, preserves server order and handles missing fields', async () => {
    const fetch = mockServer(() => json(result({ items: [song(2, 'Zebra'), song(1, 'Alpha')], total: 2 })))
    render(<SearchPage onSessionExpired={vi.fn()} />)
    await screen.findByText('2 songs found')
    expect(screen.getAllByRole('listitem').map((row) => row.querySelector('strong')?.textContent)).toEqual(['Zebra', 'Alpha'])
    expect(screen.getAllByText('Album unknown')).toHaveLength(2)
    expect(lastParams(fetch).get('page')).toBe('1')
    expect(lastParams(fetch).get('page_size')).toBe('20')
    expect(fetch.mock.calls[0][1]?.credentials).toBe('include')
    expect(button('Previous').disabled).toBe(true)
    expect(button('Next').disabled).toBe(true)
  })

  it('submits all trimmed filters with safe URL encoding and clears them', async () => {
    const fetch = mockServer()
    const user = userEvent.setup()
    render(<SearchPage onSessionExpired={vi.fn()} />)
    await screen.findByText('1 song found')
    await user.type(screen.getByLabelText('Search title, artist or album'), '  100% & more  ')
    await user.type(screen.getByLabelText('Artist'), '  A/B  ')
    await user.type(screen.getByLabelText('Album'), '  Night + Day  ')
    await user.type(screen.getByLabelText('Provider'), '  manual  ')
    expect(fetch).toHaveBeenCalledTimes(1)
    await user.click(button('Search'))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(Object.fromEntries(lastParams(fetch))).toMatchObject({
      q: '100% & more', artist: 'A/B', album: 'Night + Day', provider: 'manual', page: '1',
    })
    await user.click(button('Clear filters'))
    await waitFor(() => expect(lastParams(fetch).has('q')).toBe(false))
    expect(lastParams(fetch).has('artist')).toBe(false)
    expect(lastParams(fetch).has('album')).toBe(false)
    expect(lastParams(fetch).has('provider')).toBe(false)
    expect(screen.getByLabelText<HTMLInputElement>('Artist').value).toBe('')
  })

  it('shows applied filters while keeping unsubmitted edits separate from results', async () => {
    const fetch = mockServer()
    const user = userEvent.setup()
    render(<SearchPage onSessionExpired={vi.fn()} />)
    await screen.findByText('1 song found')
    expect(screen.getByText('Applied filters:').parentElement?.textContent).toBe('Applied filters: None')

    await user.type(screen.getByLabelText('Artist'), 'Demo Ensemble')
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Applied filters:').parentElement?.textContent).toBe('Applied filters: None')

    await user.click(button('Search'))
    await waitFor(() => expect(screen.getByText('Applied filters:').parentElement?.textContent)
      .toBe('Applied filters: Artist: Demo Ensemble'))
    await user.clear(screen.getByLabelText('Artist'))
    await user.type(screen.getByLabelText('Artist'), 'Demo Quartet')
    await user.selectOptions(screen.getByLabelText('Sort by'), 'artist')
    await waitFor(() => expect(lastParams(fetch).get('sort')).toBe('artist'))
    expect(lastParams(fetch).get('artist')).toBe('Demo Ensemble')
    expect(screen.getByText('Applied filters:').parentElement?.textContent)
      .toBe('Applied filters: Artist: Demo Ensemble')

    await user.click(button('Search'))
    await waitFor(() => expect(screen.getByText('Applied filters:').parentElement?.textContent)
      .toBe('Applied filters: Artist: Demo Quartet'))
  })

  it('uses server totals to navigate pages and disables the last page button', async () => {
    const fetch = mockServer(multiPage)
    const user = userEvent.setup()
    render(<SearchPage onSessionExpired={vi.fn()} />)
    await screen.findByText('Page 1 of 2')
    await user.click(button('Next'))
    await screen.findByText('Page 2 of 2')
    const status = screen.getByRole('status')
    expect(status.getAttribute('aria-live')).toBe('polite')
    expect(status.getAttribute('aria-atomic')).toBe('true')
    expect(status.textContent).toBe('21 songs found · Page 2 of 2')
    expect(status.textContent).not.toContain('Result page 2')
    expect(lastParams(fetch).get('page')).toBe('2')
    expect(screen.queryByText('Result page 1')).toBeNull()
    expect(button('Next').disabled).toBe(true)
    expect(button('Previous').disabled).toBe(false)
    await user.click(button('Previous'))
    await screen.findByText('Page 1 of 2')
  })

  it.each([
    ['Sort by', 'artist', 'sort'],
    ['Sort by', 'created_at', 'sort'],
    ['Direction', 'desc', 'order'],
    ['Results per page', '10', 'page_size'],
  ])('changing %s resets to page one', async (label, value, parameter) => {
    const fetch = mockServer(multiPage)
    const user = userEvent.setup()
    render(<SearchPage onSessionExpired={vi.fn()} />)
    await screen.findByText('Page 1 of 2')
    await user.click(button('Next'))
    await screen.findByText('Page 2 of 2')
    await user.selectOptions(screen.getByLabelText(label), value)
    await waitFor(() => expect(lastParams(fetch).get(parameter)).toBe(value))
    expect(lastParams(fetch).get('page')).toBe('1')
  })

  it('applying filters resets the page and preserves sort and page size', async () => {
    const fetch = mockServer(multiPage)
    const user = userEvent.setup()
    render(<SearchPage onSessionExpired={vi.fn()} />)
    await screen.findByText('Page 1 of 2')
    await user.selectOptions(screen.getByLabelText('Sort by'), 'artist')
    await user.selectOptions(screen.getByLabelText('Results per page'), '10')
    await screen.findByText('Page 1 of 3')
    await user.click(button('Next'))
    await screen.findByText('Page 2 of 3')
    await user.type(screen.getByLabelText('Artist'), 'Ensemble')
    await user.click(button('Search'))
    await screen.findByText('Page 1 of 3')
    expect(Object.fromEntries(lastParams(fetch))).toMatchObject({ artist: 'Ensemble', sort: 'artist', page_size: '10', page: '1' })
  })

  it('shows loading and empty states without enabling pagination', async () => {
    let resolve!: (response: Response) => void
    mockServer(() => new Promise<Response>((done) => { resolve = done }))
    render(<SearchPage onSessionExpired={vi.fn()} />)
    expect(screen.getByText('Loading songs…')).toBeTruthy()
    expect(button('Next').disabled).toBe(true)
    await act(async () => resolve(json(result({ items: [], total: 0, total_pages: 0 }))))
    expect(screen.getByText('0 songs found')).toBeTruthy()
    expect(screen.getByText(/No songs match/)).toBeTruthy()
    expect(screen.queryByRole('list', { name: 'Search results' })).toBeNull()
    expect(button('Previous').disabled).toBe(true)
  })

  it('handles a page emptied by a catalog change and allows returning', async () => {
    mockServer((params) => Number(params.get('page')) === 1 ? multiPage(params)
      : json(result({ items: [], page: 2 })))
    const user = userEvent.setup()
    render(<SearchPage onSessionExpired={vi.fn()} />)
    await screen.findByText('Page 1 of 2')
    await user.click(button('Next'))
    await screen.findByText(/This page is empty/)
    expect(button('Previous').disabled).toBe(false)
    expect(button('Next').disabled).toBe(true)
  })

  it('renders errors and retries without claiming there were no results', async () => {
    let failing = true
    mockServer(() => failing ? json({ detail: 'Search temporarily unavailable' }, 503) : json(result()))
    const user = userEvent.setup()
    render(<SearchPage onSessionExpired={vi.fn()} />)
    expect((await screen.findByRole('alert')).textContent).toContain('Search temporarily unavailable')
    expect(screen.queryByText(/No songs match/)).toBeNull()
    expect(button('Next').disabled).toBe(true)
    failing = false
    await user.click(button('Retry'))
    await screen.findByText('1 song found')
  })

  it('shows backend validation errors', async () => {
    mockServer(() => json({ detail: [{ loc: ['query', 'q'], msg: 'String should have at most 200 characters' }] }, 422))
    render(<SearchPage onSessionExpired={vi.fn()} />)
    expect((await screen.findByRole('alert')).textContent).toContain('q: String should have at most 200 characters')
  })

  it('hands expired sessions back to the app', async () => {
    mockServer(() => json({ detail: 'Unauthorized' }, 401))
    const expired = vi.fn()
    render(<SearchPage onSessionExpired={expired} />)
    await waitFor(() => expect(expired).toHaveBeenCalledOnce())
  })

  it('aborts superseded requests and ignores stale successes and failures', async () => {
    const pending: { resolve: (value: Response) => void; reject: (reason: Error) => void }[] = []
    const fetch = mockServer(() => new Promise<Response>((resolve, reject) => pending.push({ resolve, reject })))
    const expired = vi.fn()
    const user = userEvent.setup()
    const view = render(<SearchPage onSessionExpired={expired} />)
    await user.selectOptions(screen.getByLabelText('Direction'), 'desc')
    await user.selectOptions(screen.getByLabelText('Sort by'), 'artist')
    expect(fetch.mock.calls[0][1]?.signal?.aborted).toBe(true)
    await act(async () => pending[2].resolve(json(result({ items: [song(3, 'Current result')] }))))
    await act(async () => pending[0].resolve(json(result({ items: [song(1, 'Stale result')] }))))
    await act(async () => pending[1].reject(new Error('Stale failure')))
    expect(screen.getByText('Current result')).toBeTruthy()
    expect(screen.queryByText('Stale result')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(expired).not.toHaveBeenCalled()
    view.unmount()
    expect(fetch.mock.calls[2][1]?.signal?.aborted).toBe(true)
  })

  it('supports direct navigation and the sidebar Search link in the authenticated app', async () => {
    mockServer()
    window.history.replaceState({}, '', '/search')
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('heading', { name: 'Search songs' })
    const nav = screen.getByRole('navigation', { name: 'Main navigation' })
    expect(within(nav).getByRole('link', { name: 'Search' }).getAttribute('aria-current')).toBe('page')
    await user.click(within(nav).getByRole('link', { name: 'Home' }))
    await screen.findByRole('heading', { name: 'Your Top 10' })
    await user.click(within(nav).getByRole('link', { name: 'Search' }))
    await screen.findByRole('heading', { name: 'Search songs' })
    expect(window.location.pathname).toBe('/search')
  })
})
