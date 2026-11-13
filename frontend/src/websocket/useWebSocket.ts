import { useEffect, useState } from 'react'
import { connectWebSocket } from './client.ts'

const emptyOnlineIds = new Set<number>()

export type PresenceStatus =
  | 'disabled'
  | 'connecting'
  | 'ready'
  | 'reconnecting'
  | 'login-required'

type PresenceMessage =
  | { type: 'presence_snapshot'; data: { online_user_ids: number[] } }
  | { type: 'presence'; data: { user_id: number; online: boolean } }

function parsePresenceMessage(value: unknown): PresenceMessage | null {
  if (typeof value !== 'string') return null

  let message: unknown
  try {
    message = JSON.parse(value)
  } catch {
    return null
  }

  if (typeof message !== 'object' || message === null || !('type' in message) || !('data' in message)) {
    return null
  }

  const candidate = message as { type: unknown; data: unknown }
  if (typeof candidate.data !== 'object' || candidate.data === null) return null

  if (candidate.type === 'presence_snapshot' && 'online_user_ids' in candidate.data) {
    const ids = (candidate.data as { online_user_ids: unknown }).online_user_ids
    if (Array.isArray(ids) && ids.every((id) => Number.isSafeInteger(id) && id > 0)) {
      return { type: 'presence_snapshot', data: { online_user_ids: ids as number[] } }
    }
  }

  if (candidate.type === 'presence' && 'user_id' in candidate.data && 'online' in candidate.data) {
    const data = candidate.data as { user_id: unknown; online: unknown }
    if (Number.isSafeInteger(data.user_id) && Number(data.user_id) > 0 && typeof data.online === 'boolean') {
      return { type: 'presence', data: { user_id: Number(data.user_id), online: data.online } }
    }
  }

  return null
}

export function useWebSocket(enabled: boolean) {
  const [status, setStatus] = useState<PresenceStatus>('disabled')
  const [onlineIds, setOnlineIds] = useState<Set<number>>(() => new Set())

  useEffect(() => {
    if (!enabled) return

    let stopped = false
    let socket: WebSocket | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let snapshotTimer: ReturnType<typeof setTimeout> | null = null
    let attempts = 0
    const requests = new AbortController()

    const clearSnapshotTimer = () => {
      if (snapshotTimer !== null) clearTimeout(snapshotTimer)
      snapshotTimer = null
    }

    const clearRetryTimer = () => {
      if (retryTimer !== null) clearTimeout(retryTimer)
      retryTimer = null
    }

    const markUnknown = (nextStatus: PresenceStatus) => {
      setOnlineIds(new Set())
      setStatus(nextStatus)
    }

    const scheduleRetry = () => {
      if (stopped || retryTimer !== null) return
      markUnknown('reconnecting')
      const cap = Math.min(30_000, 1_000 * 2 ** Math.min(attempts++, 5))
      retryTimer = setTimeout(() => {
        retryTimer = null
        void connect()
      }, cap * (0.5 + Math.random() / 2))
    }

    const connect = async () => {
      if (stopped) return
      clearRetryTimer()
      markUnknown(attempts === 0 ? 'connecting' : 'reconnecting')

      try {
        const response = await fetch('/api/v1/auth/me', {
          credentials: 'include',
          cache: 'no-store',
          signal: requests.signal,
        })
        if (stopped) return
        if (response.status === 401) {
          markUnknown('login-required')
          stopped = true
          return
        }
        if (!response.ok) {
          scheduleRetry()
          return
        }
      } catch {
        if (!stopped) scheduleRetry()
        return
      }

      if (stopped) return
      let current: WebSocket
      try {
        current = connectWebSocket()
      } catch {
        scheduleRetry()
        return
      }
      socket = current
      let synchronized = false

      snapshotTimer = setTimeout(() => {
        if (!stopped && socket === current && !synchronized) current.close()
      }, 30_000)

      current.addEventListener('message', (event: MessageEvent<unknown>) => {
        if (stopped || socket !== current) return
        const message = parsePresenceMessage(event.data)
        if (!message) return

        if (message.type === 'presence_snapshot') {
          synchronized = true
          attempts = 0
          clearSnapshotTimer()
          setOnlineIds(new Set(message.data.online_user_ids))
          setStatus('ready')
          return
        }

        if (!synchronized) return
        setOnlineIds((currentIds) => {
          const nextIds = new Set(currentIds)
          if (message.data.online) nextIds.add(message.data.user_id)
          else nextIds.delete(message.data.user_id)
          return nextIds
        })
      })

      current.addEventListener('close', (event: CloseEvent) => {
        if (stopped || socket !== current) return
        clearSnapshotTimer()
        socket = null
        if (event.code === 1008) {
          markUnknown('login-required')
          stopped = true
          return
        }
        scheduleRetry()
      })

      current.addEventListener('error', () => {
        // The browser follows a failed upgrade with close; retry only there.
      })
    }

    void connect()

    return () => {
      stopped = true
      requests.abort()
      clearRetryTimer()
      clearSnapshotTimer()
      if (socket !== null) socket.close()
      socket = null
    }
  }, [enabled])

  return { status: enabled ? status : 'disabled', onlineIds: enabled ? onlineIds : emptyOnlineIds }
}
