import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import NotificationBell from '../src/components/NotificationBell.tsx'
import Shell from '../src/components/Shell.tsx'
import { deferred, json, notification, notificationsServer } from './notificationsServer.ts'

async function open(count: number) {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: `Notifications, ${count} unread` }))
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Refresh' }).disabled).toBe(false))
  return user
}

function renderBell(revision = 0, onSessionExpired = vi.fn()) {
  return render(<NotificationBell revision={revision} connectionStatus="ready" onSessionExpired={onSessionExpired} />)
}

describe('notification interface', () => {
  it('fetches on initial load, displays server order, readable times and explicit read status', async () => {
    const { fetch } = notificationsServer([
      notification(2, { message: 'A comment was updated.' }),
      notification(1, { message: 'A friend request was accepted.', read_at: '2026-11-22T13:00:00Z' }),
    ])
    renderBell()
    await open(1)
    expect(screen.getAllByRole('listitem').map((row) => row.querySelector('p')?.textContent))
      .toEqual(['A comment was updated.', 'A friend request was accepted.'])
    expect(screen.getByText('Unread')).toBeTruthy()
    expect(screen.getByText('Read')).toBeTruthy()
    expect(document.querySelector('time')?.getAttribute('datetime')).toBe('2026-11-22T12:30:00+00:00')
    for (const [url, init] of fetch.mock.calls) {
      expect(String(url)).not.toMatch(/recipient_id|user_id/)
      expect(init?.credentials).toBe('include')
      expect(init?.cache).toBe('no-store')
    }
  })

  it('marks as read with POST, then reloads list and unread count through REST', async () => {
    const { fetch } = notificationsServer([notification(1)])
    renderBell()
    const user = await open(1)
    await user.click(screen.getByRole('button', { name: 'Mark as read: Notification 1' }))
    await screen.findByRole('button', { name: 'Notifications, 0 unread' })
    expect(screen.queryByRole('button', { name: /Mark as read:/ })).toBeNull()
    expect(screen.getByText('Read')).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByRole('region', { name: 'Notifications' }))
    expect(fetch.mock.calls.filter(([url, init]) => String(url).endsWith('/1/read') && init?.method === 'POST')).toHaveLength(1)
  })

  it('shows an empty state, keyboard disclosure controls, Escape dismissal and focus restoration', async () => {
    notificationsServer()
    renderBell()
    const user = await open(0)
    expect(screen.getByText('No notifications yet.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Notifications, 0 unread' }).getAttribute('aria-expanded')).toBe('true')
    await user.tab()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Close' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('region', { name: 'Notifications' })).toBeNull()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Notifications, 0 unread' }))
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('region', { name: 'Notifications' })).toBeTruthy()
    await user.click(document.body)
    expect(screen.queryByRole('region', { name: 'Notifications' })).toBeNull()
  })

  it('paginates in bounded pages without appending duplicate rows', async () => {
    const { fetch } = notificationsServer(Array.from({ length: 25 }, (_, index) => notification(25 - index)))
    renderBell()
    const user = await open(25)
    expect(screen.getAllByRole('listitem')).toHaveLength(20)
    await user.click(screen.getByRole('button', { name: 'Older' }))
    await screen.findByText('Notification 1')
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
    expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Older' }).disabled).toBe(true)
    expect(screen.getByText('Page 2')).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Newer' }))
    await screen.findByText('Notification 25')
    expect(screen.getAllByRole('listitem')).toHaveLength(20)
    expect(fetch.mock.calls.some(([url]) => String(url).includes('limit=21&offset=20'))).toBe(true)
  })

  it('returns to the newest page when a notification revision arrives', async () => {
    const { server } = notificationsServer(Array.from({ length: 25 }, (_, index) => notification(25 - index)))
    const expired = vi.fn()
    const view = renderBell(0, expired)
    const user = await open(25)
    await user.click(screen.getByRole('button', { name: 'Older' }))
    await screen.findByText('Notification 1')
    server.items.unshift(notification(26))
    view.rerender(<NotificationBell revision={1} connectionStatus="ready" onSessionExpired={expired} />)
    await screen.findByText('Notification 26')
    expect(screen.getByText('Page 1')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Notifications, 26 unread' })).toBeTruthy()
  })

  it('shows request errors and retries without claiming an empty inbox', async () => {
    const { server } = notificationsServer([notification(1)])
    server.listStatus = 503
    renderBell()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /Notifications,/ }))
    await screen.findByRole('alert')
    expect(screen.queryByText('No notifications yet.')).toBeNull()
    server.listStatus = 200
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    await screen.findByText('Notification 1')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('keeps an unread notification and offers retry if marking it fails', async () => {
    const { server } = notificationsServer([notification(1)])
    server.readStatus = 500
    renderBell()
    const user = await open(1)
    await user.click(screen.getByRole('button', { name: 'Mark as read: Notification 1' }))
    await screen.findByRole('alert')
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Mark as read: Notification 1' }).disabled).toBe(false))
    expect(screen.getByText('Unread')).toBeTruthy()
    server.readStatus = 200
    await user.click(screen.getByRole('button', { name: 'Mark as read: Notification 1' }))
    await screen.findByText('Read')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('treats notification messages as text, not HTML', async () => {
    notificationsServer([notification(1, { message: '<img src=x onerror=alert(1)>' })])
    renderBell()
    await open(1)
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeTruthy()
    expect(document.querySelector('.notification-list img')).toBeNull()
  })

  it('clears notification content on an expired session', async () => {
    const { server } = notificationsServer([notification(1)])
    const expired = vi.fn()
    renderBell(0, expired)
    const user = await open(1)
    server.listStatus = 401
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(expired).toHaveBeenCalledOnce())
    expect(screen.queryByText('Notification 1')).toBeNull()
  })

  it('shows loading while requests are pending', async () => {
    const pending = deferred<Response>()
    vi.stubGlobal('fetch', vi.fn(() => pending.promise))
    const view = renderBell()
    await userEvent.setup().click(screen.getByRole('button', { name: /Notifications,/ }))
    expect(screen.getByText('Loading notifications…')).toBeTruthy()
    expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Refresh' }).disabled).toBe(true)
    view.unmount()
    await act(async () => pending.resolve(json([])))
  })

  it('discards cached data and late responses when the authenticated user changes', async () => {
    const { server, fetch } = notificationsServer([notification(1, { message: 'Alice only' })])
    const expired = vi.fn()
    const shell = (id: number) => <Shell path="/" theme="light" user={{ id, display_name: `User ${id}` }}
      headerNotice="" onToggleTheme={() => {}} onLogout={async () => {}}
      notificationRevision={0} connectionStatus="ready" onSessionExpired={expired}>Page</Shell>
    const view = render(shell(1))
    const user = await open(1)
    expect(screen.getByText('Alice only')).toBeTruthy()
    const oldResponse = deferred<Response>()
    fetch.mockImplementationOnce(() => oldResponse.promise)
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    const oldSignal = fetch.mock.calls.at(-2)?.[1]?.signal
    server.items = [notification(2, { message: 'Bob only' })]
    view.rerender(shell(2))
    expect(screen.queryByText('Alice only')).toBeNull()
    expect(oldSignal?.aborted).toBe(true)
    await open(1)
    await screen.findByText('Bob only')
    await act(async () => oldResponse.resolve(json([notification(1, { message: 'Alice only' })])))
    expect(screen.queryByText('Alice only')).toBeNull()
    expect(screen.getByText('Bob only')).toBeTruthy()
    expect(expired).not.toHaveBeenCalled()
  })

  it('does not let a superseded refresh overwrite more recent notification state', async () => {
    const { server, fetch } = notificationsServer([notification(1)])
    const expired = vi.fn()
    const view = renderBell(0, expired)
    const user = await open(1)
    const old = deferred<Response>()
    fetch.mockImplementationOnce(() => old.promise)
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    server.items.unshift(notification(2))
    view.rerender(<NotificationBell revision={1} connectionStatus="ready" onSessionExpired={expired} />)
    await screen.findByText('Notification 2')
    await act(async () => old.resolve(json([notification(1)])))
    expect(screen.getByText('Notification 2')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Notifications, 2 unread' })).toBeTruthy()
  })

  it('resynchronizes after a live event arrives during an in-flight read mutation', async () => {
    const { server, fetch } = notificationsServer([notification(1)])
    const expired = vi.fn()
    const view = renderBell(0, expired)
    const user = await open(1)
    const read = deferred<Response>()
    fetch.mockImplementationOnce(() => read.promise)
    await user.click(screen.getByRole('button', { name: 'Mark as read: Notification 1' }))
    const updated = notification(1, { read_at: '2026-11-22T14:00:00Z' })
    server.items = [notification(2), updated]
    view.rerender(<NotificationBell revision={1} connectionStatus="ready" onSessionExpired={expired} />)
    await act(async () => read.resolve(json(updated)))
    await screen.findByText('Notification 2')
    await screen.findByRole('button', { name: 'Notifications, 1 unread' })
    expect(screen.queryByRole('button', { name: 'Mark as read: Notification 1' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Mark as read: Notification 2' })).toBeTruthy()
  })

  it('cancels pending mutations on logout and ignores their late authentication errors', async () => {
    const { fetch } = notificationsServer([notification(1)])
    const expired = vi.fn()
    const view = renderBell(0, expired)
    const user = await open(1)
    const read = deferred<Response>()
    fetch.mockImplementationOnce(() => read.promise)
    await user.click(screen.getByRole('button', { name: 'Mark as read: Notification 1' }))
    const signal = fetch.mock.calls.at(-1)?.[1]?.signal
    view.unmount()
    expect(signal?.aborted).toBe(true)
    await act(async () => read.resolve(json({ detail: 'Expired session' }, 401)))
    expect(expired).not.toHaveBeenCalled()
  })
})
