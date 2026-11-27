import { useEffect, useRef, useState } from 'react'

import { ApiError } from '../lib/api.ts'
import {
  fetchNotifications, markNotificationRead, MAX_NOTIFICATION_OFFSET,
  NOTIFICATION_PAGE_SIZE, type UserNotification,
} from '../lib/notificationsApi.ts'

type NotificationState = {
  items: UserNotification[]
  unreadCount: number | null
  hasMore: boolean
  revision: number
  loading: boolean
  error: string
}


export default function useNotifications(revision: number, onSessionExpired: () => void) {
  const [page, setPage] = useState({ offset: 0, revision })
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [readingId, setReadingId] = useState<number | null>(null)
  const [actionError, setActionError] = useState('')
  const [state, setState] = useState<NotificationState>({
    items: [], unreadCount: null, hasMore: false, revision, loading: true, error: '',
  })
  const loadRequest = useRef<AbortController | null>(null)
  const readRequest = useRef<AbortController | null>(null)

  const offset = page.revision === revision ? page.offset : 0

  useEffect(() => {
    if (readingId !== null) return
    const request = new AbortController()
    loadRequest.current = request
    setState((previous) => ({ ...previous, loading: true, error: '' }))

    void fetchNotifications(offset, request.signal).then((result) => {
      if (request.signal.aborted) return
      setState((previous) => {
        let items = result.items

        if (offset > 0 && previous.revision === revision) {
          const loadedIds = new Set(previous.items.map((item) => item.id))
          const olderItems = result.items.filter((item) => !loadedIds.has(item.id))
          items = [...previous.items, ...olderItems]
        }

        return { ...result, items, revision, loading: false, error: '' }
      })
    }).catch((error: unknown) => {
      if (request.signal.aborted) return
      if (error instanceof ApiError && error.status === 401) {
        setState({ items: [], unreadCount: null, hasMore: false, revision, loading: false, error: '' })
        onSessionExpired()
        return
      }
      setState((previous) => ({
        ...previous,
        items: previous.revision === revision ? previous.items : [],
        unreadCount: null, revision, loading: false,
        error: 'Could not refresh notifications. Please try again.',
      }))
    })

    return () => request.abort()
  }, [offset, revision, refreshVersion, readingId, onSessionExpired])

  useEffect(() => () => {
    loadRequest.current?.abort()
    readRequest.current?.abort()
  }, [])

  function refresh() {
    setActionError('')
    setPage({ offset: 0, revision })
    setRefreshVersion((value) => value + 1)
  }

  function newest() {
    refresh()
  }

  async function markRead(id: number) {
    if (readRequest.current !== null || state.loading) return
    const item = state.items.find((item) => item.id === id)
    if (!item || item.read_at !== null) return

    loadRequest.current?.abort()
    const request = new AbortController()
    readRequest.current = request
    setReadingId(id)
    setActionError('')
    try {
      const updated = await markNotificationRead(id, request.signal)
      if (request.signal.aborted) return
      setState((previous) => ({
        ...previous,
        items: previous.items.map((item) => item.id === id ? { ...item, read_at: updated.read_at } : item),
      }))
    } catch (error) {
      if (request.signal.aborted) return
      if (error instanceof ApiError && error.status === 401) {
        setState((previous) => ({ ...previous, items: [], unreadCount: null }))
        onSessionExpired()
      } else {
        setActionError('Could not mark this notification as read. Please try again.')
      }
    } finally {
      if (!request.signal.aborted) {
        readRequest.current = null

        setState((previous) => ({ ...previous, loading: true }))
        setReadingId(null)
      }
    }
  }

  const currentRevision = state.revision === revision
  const loadingMore = currentRevision && state.loading && offset > 0
  return {
    items: currentRevision ? state.items : [],
    unreadCount: state.unreadCount,
    loading: !currentRevision || (state.loading && offset === 0),
    loadingMore,
    error: state.error,
    actionError,
    readingId,
    hasOlder: currentRevision && state.hasMore && offset < MAX_NOTIFICATION_OFFSET,
    refresh,
    newest,
    older: () => {
      if (!state.loading && state.hasMore) {
        setPage({ offset: Math.min(MAX_NOTIFICATION_OFFSET, offset + NOTIFICATION_PAGE_SIZE), revision })
      }
    },
    markRead,
  }
}
