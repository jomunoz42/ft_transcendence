import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode } from 'react'
import { beforeEach, expect, it, vi } from 'vitest'

import NotificationBell from '../src/components/NotificationBell.tsx'
import { useWebSocket } from '../src/websocket/useWebSocket.ts'
import { notification, notificationsServer } from './notificationsServer.ts'

class Socket extends EventTarget {
  static instances: Socket[] = []
  close = vi.fn()
  url: string
  constructor(url: string) {
    super()
    this.url = url
    Socket.instances.push(this)
  }
  message(value: unknown) {
    this.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(value) }))
  }
  disconnect(code = 1006) {
    this.dispatchEvent(new CloseEvent('close', { code }))
  }
}

const expired = vi.fn()
function ConnectedNotifications({ enabled = true, userId = 1 }) {
  const socket = useWebSocket(enabled, userId)
  return <>
    <output aria-label="Connection status">{socket.status}</output>
    <output aria-label="Online friends">{[...socket.onlineIds].join(',')}</output>
    {enabled && <NotificationBell key={userId} revision={socket.notificationRevision}
      connectionStatus={socket.status} onSessionExpired={expired} />}
  </>
}

beforeEach(() => {
  Socket.instances = []
  vi.stubGlobal('WebSocket', Socket)
  expired.mockClear()
})

async function connect() {
  await waitFor(() => expect(Socket.instances).toHaveLength(1))
  await act(async () => Socket.instances[0].message({ type: 'presence_snapshot', data: { online_user_ids: [5] } }))
  await screen.findByRole('button', { name: 'Notifications, 1 unread' })
}

it('uses one socket and refreshes REST for notification signals without trusting their content', async () => {
  const { server, fetch } = notificationsServer([notification(1)])
  render(<StrictMode><ConnectedNotifications /></StrictMode>)
  await connect()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Notifications, 1 unread' }))
  await screen.findByText('Notification 1')
  const before = fetch.mock.calls.length
  server.items.unshift(notification(2, { message: 'Message from REST' }))
  await act(async () => Socket.instances[0].message({
    type: 'notification', data: { id: 2, message: 'Forged WebSocket content', recipient_id: 999, unread_count: 999 },
  }))
  await screen.findByText('Message from REST')
  expect(screen.getByRole('button', { name: 'Notifications, 2 unread' })).toBeTruthy()
  expect(screen.queryByText('Forged WebSocket content')).toBeNull()
  expect(fetch.mock.calls.length).toBeGreaterThan(before)
  expect(Socket.instances).toHaveLength(1)
  expect(screen.getByLabelText('Online friends').textContent).toBe('5')
})

it('resynchronizes offline notifications after reconnection and the first presence snapshot', async () => {
  vi.spyOn(Math, 'random').mockReturnValue(0)
  const { server } = notificationsServer([notification(1)])
  render(<ConnectedNotifications />)
  await connect()
  await act(async () => Socket.instances[0].disconnect())
  server.items.unshift(notification(2))
  await waitFor(() => expect(Socket.instances).toHaveLength(2), { timeout: 2000 })
  await act(async () => Socket.instances[1].message({ type: 'presence_snapshot', data: { online_user_ids: [] } }))
  await screen.findByRole('button', { name: 'Notifications, 2 unread' })
  expect(screen.getByLabelText('Connection status').textContent).toBe('ready')
})

it('ignores malformed notifications, retains presence behavior, and does not refetch on periodic snapshots', async () => {
  const { fetch } = notificationsServer([notification(1)])
  render(<ConnectedNotifications />)
  await connect()
  const before = fetch.mock.calls.length
  await act(async () => {
    for (const id of [null, '2', -1, 0]) Socket.instances[0].message({ type: 'notification', data: { id } })
    Socket.instances[0].message({ type: 'notification', data: null })
    Socket.instances[0].message({ type: 'presence_snapshot', data: { online_user_ids: [8] } })
    Socket.instances[0].message({ type: 'presence', data: { user_id: 9, online: true } })
  })
  expect(fetch.mock.calls).toHaveLength(before)
  expect(screen.getByLabelText('Online friends').textContent).toBe('8,9')
})

it('closes the old account socket and ignores stale frames on account changes and logout', async () => {
  notificationsServer([notification(1)])
  const view = render(<ConnectedNotifications />)
  await connect()
  const old = Socket.instances[0]
  view.rerender(<ConnectedNotifications userId={2} />)
  await waitFor(() => expect(Socket.instances).toHaveLength(2))
  expect(old.close).toHaveBeenCalledOnce()
  view.rerender(<ConnectedNotifications enabled={false} userId={2} />)
  expect(Socket.instances[1].close).toHaveBeenCalledOnce()
  await act(async () => old.message({ type: 'notification', data: { id: 123 } }))
  expect(screen.queryByRole('button', { name: /Notifications,/ })).toBeNull()
  expect(screen.getByLabelText('Connection status').textContent).toBe('disabled')
})

it('revalidates notification authentication when the socket requires login', async () => {
  const { server } = notificationsServer([notification(1)])
  render(<ConnectedNotifications />)
  await connect()
  server.listStatus = 401
  await act(async () => Socket.instances[0].disconnect(1008))
  await waitFor(() => expect(expired).toHaveBeenCalledOnce())
  expect(screen.getByLabelText('Connection status').textContent).toBe('login-required')
})
