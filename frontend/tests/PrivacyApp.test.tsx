import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'

import App from '../src/app/App.tsx'
import { json } from './notificationsServer.ts'

vi.mock('../src/components/NotificationBell.tsx', () => ({ default: () => null }))

class Socket extends EventTarget {
  static instances: Socket[] = []
  close = vi.fn()
  constructor() {
    super()
    Socket.instances.push(this)
  }
}

beforeEach(() => {
  Socket.instances = []
  window.localStorage.clear()
  window.localStorage.setItem('myplaylist-blocked-users-1', '[2]')
  window.history.replaceState({}, '', '/settings')
  vi.stubGlobal('WebSocket', Socket)
})

it('clears account state and browser cache, closes the socket, and protects settings after deletion', async () => {
  let deleted = false
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input), 'https://testserver').pathname
    if (path === '/api/v1/auth/me') {
      return deleted ? json({ detail: 'Not authenticated' }, 401) : json({ id: 1, display_name: 'Alice' })
    }
    if (path === '/api/v1/profiles/me') {
      return json({ display_name: 'Alice', bio: '', is_top10_public: false })
    }
    if (path === '/api/v1/privacy/deletion-request') {
      return json({ detail: 'Check email', expires_at: '2026-11-24T22:15:00+00:00', cooldown_seconds: 300 }, 202)
    }
    if (path === '/api/v1/privacy/deletion-confirm' && init?.method === 'POST') {
      deleted = true
      return new Response(null, { status: 204 })
    }
    throw new Error(`Unexpected request: ${path}`)
  })
  vi.stubGlobal('fetch', fetch)

  render(<App />)
  const user = userEvent.setup()
  await screen.findByRole('heading', { name: 'Privacy and account' })
  expect(fetch).toHaveBeenCalledWith('/api/v1/auth/me', expect.objectContaining({ cache: 'no-store' }))
  await waitFor(() => expect(Socket.instances.length).toBe(1))
  await user.click(screen.getByRole('button', { name: 'Email me a deletion token' }))
  await screen.findByLabelText('Token from your email')
  await user.type(screen.getByLabelText('Token from your email'), 'private-token')
  await user.type(screen.getByRole('textbox', { name: /Type DELETE/ }), 'DELETE')
  await user.click(screen.getByRole('button', { name: 'Permanently delete account' }))

  await waitFor(() => expect(window.location.pathname).toBe('/login'))
  await waitFor(() => expect(Socket.instances[0].close).toHaveBeenCalled())
  expect(window.localStorage.getItem('myplaylist-blocked-users-1')).toBeNull()
  expect(screen.queryByRole('heading', { name: 'Privacy and account' })).toBeNull()

  act(() => {
    window.history.pushState({}, '', '/settings')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  await waitFor(() => expect(window.location.pathname).toBe('/login'))
  expect(screen.queryByRole('heading', { name: 'Privacy and account' })).toBeNull()
})
