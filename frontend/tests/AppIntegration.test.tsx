import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'

import App from '../src/app/App.tsx'
import { json, notification, notificationsServer } from './notificationsServer.ts'

// Keep these integration checks focused on routing, session handling and the shell.
vi.mock('../src/pages/HomePage.tsx', () => ({ default: () => <p>Home content</p> }))

class Socket extends EventTarget {
  close = vi.fn()
}

beforeEach(() => {
  window.localStorage.clear()
  window.history.replaceState({}, '', '/')
  vi.stubGlobal('WebSocket', Socket)
})

function expectLegalFooter() {
  const footer = within(screen.getByRole('contentinfo', { name: 'Legal information' }))
  expect(footer.getByRole('link', { name: 'Privacy Policy' }).getAttribute('href')).toBe('/privacy')
  expect(footer.getByRole('link', { name: 'Terms of Service' }).getAttribute('href')).toBe('/terms')
}

it.each([
  ['/privacy', 'Privacy Policy', false],
  ['/terms', 'Terms of Service', false],
  ['/privacy', 'Privacy Policy', true],
  ['/terms', 'Terms of Service', true],
] as const)('keeps %s (%s) public with authenticated=%s', async (path, heading, authenticated) => {
  window.history.replaceState({}, '', path)
  vi.stubGlobal('fetch', vi.fn(async () => authenticated
    ? json({ id: 1, display_name: 'Alice' })
    : json({ detail: 'Not logged in' }, 401)))
  render(<App />)
  expect(await screen.findByRole('heading', { name: heading, level: 1 })).toBeTruthy()
  expect(window.location.pathname).toBe(path)
  expectLegalFooter()
})

it.each(['/login', '/register'])('retains the legal footer on %s', async (path) => {
  window.history.replaceState({}, '', path)
  vi.stubGlobal('fetch', vi.fn(async () => json({ detail: 'Not logged in' }, 401)))
  render(<App />)
  await screen.findByRole('contentinfo', { name: 'Legal information' })
  expectLegalFooter()
})

it('keeps notifications usable alongside footer navigation and handles session expiry', async () => {
  const { server } = notificationsServer([notification(1)])
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Notifications, 1 unread' }))
  expect(await screen.findByText('Notification 1')).toBeTruthy()
  expectLegalFooter()
  await user.click(screen.getByRole('link', { name: 'Privacy Policy' }))
  expect(await screen.findByRole('heading', { name: 'Privacy Policy', level: 1 })).toBeTruthy()
  await user.click(screen.getByRole('link', { name: 'Terms of Service' }))
  expect(await screen.findByRole('heading', { name: 'Terms of Service', level: 1 })).toBeTruthy()

  // Return to the shell through normal SPA history handling.
  act(() => {
    window.history.pushState({}, '', '/')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  await user.click(await screen.findByRole('button', { name: 'Notifications, 1 unread' }))
  await screen.findByText('Notification 1')
  server.listStatus = 401
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  await screen.findByRole('heading', { name: 'Welcome to MyPlaylist' })
  expect(window.location.pathname).toBe('/login')
  expect(screen.queryByText('Notification 1')).toBeNull()
  expectLegalFooter()
})
