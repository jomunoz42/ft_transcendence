import { vi } from 'vitest'
import type { UserNotification } from '../src/lib/notificationsApi.ts'

export function notification(id: number, overrides: Partial<UserNotification> = {}): UserNotification {
  return {
    id, actor_id: 5, event_type: 'comment.created', message: `Notification ${id}`,
    created_at: '2026-11-22T12:30:00+00:00', read_at: null, ...overrides,
  }
}

export function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
}

export function notificationsServer(initial: UserNotification[] = []) {
  const server = { items: initial, listStatus: 200, readStatus: 200 }
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'https://testserver')
    if (url.pathname === '/api/v1/auth/me') return json({ id: 1, display_name: 'Alice' })
    if (url.pathname === '/api/v1/notifications/unread-count') {
      return json({ unread_count: server.items.filter((item) => item.read_at === null).length })
    }
    if (url.pathname === '/api/v1/notifications') {
      if (server.listStatus !== 200) return json({ detail: 'Test error' }, server.listStatus)
      const offset = Number(url.searchParams.get('offset'))
      const limit = Number(url.searchParams.get('limit'))
      return json(server.items.slice(offset, offset + limit))
    }
    const match = url.pathname.match(/^\/api\/v1\/notifications\/(\d+)\/read$/)
    if (match && init?.method === 'POST') {
      if (server.readStatus !== 200) return json({ detail: 'Test error' }, server.readStatus)
      server.items = server.items.map((item) => item.id === Number(match[1])
        ? { ...item, read_at: '2026-11-22T13:00:00+00:00' } : item)
      return json(server.items.find((item) => item.id === Number(match[1])))
    }
    throw new Error(`Unexpected request: ${url.pathname}`)
  })
  vi.stubGlobal('fetch', fetch)
  return { server, fetch }
}

export function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}
