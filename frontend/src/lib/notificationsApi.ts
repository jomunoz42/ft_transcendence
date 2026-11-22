import { api } from './api.ts'

export type UserNotification = {
  id: number
  actor_id: number | null
  event_type: string
  message: string
  created_at: string
  read_at: string | null
}

export const NOTIFICATION_PAGE_SIZE = 20
export const MAX_NOTIFICATION_OFFSET = 10_000

export async function fetchNotifications(offset: number, signal: AbortSignal) {
  // One extra row tells us whether an older page exists. Identity comes only
  // from the session cookie; no recipient/user ID is sent by the client.
  const [items, count] = await Promise.all([
    api<UserNotification[]>(
      `/api/v1/notifications?limit=${NOTIFICATION_PAGE_SIZE + 1}&offset=${offset}`,
      { signal, cache: 'no-store' },
    ),
    api<{ unread_count: number }>('/api/v1/notifications/unread-count', { signal, cache: 'no-store' }),
  ])
  return {
    items: items.slice(0, NOTIFICATION_PAGE_SIZE),
    hasMore: items.length > NOTIFICATION_PAGE_SIZE,
    unreadCount: count.unread_count,
  }
}

export function markNotificationRead(id: number, signal: AbortSignal) {
  return api<UserNotification>(`/api/v1/notifications/${id}/read`, { method: 'POST', signal })
}
