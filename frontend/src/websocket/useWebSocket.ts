import {
  useEffect,
  useState,
} from 'react'

import { connectWebSocket } from './client.ts'
import { parsePresenceMessage } from './presenceMessages.ts'

const emptyOnlineIds = new Set<number>()

export type PresenceStatus =
  | 'disabled'
  | 'connecting'
  | 'ready'
  | 'reconnecting'
  | 'login-required'

export type PresenceState = {
  status: PresenceStatus
  onlineIds: Set<number>
}

function getRetryDelay(attempt: number) {
  const limitedAttempt = Math.min(attempt, 5)
  const multiplier = Math.pow(2, limitedAttempt)
  const exponentialDelay = 1_000 * multiplier
  const cappedDelay = Math.min(30_000, exponentialDelay)

  const randomValue = Math.random()
  const jitter = 0.5 + randomValue / 2

  return cappedDelay * jitter
}

export function useWebSocket(
  enabled: boolean,
): PresenceState {
  const [status, setStatus] = useState<PresenceStatus>(
    'disabled',
  )

  const [onlineIds, setOnlineIds] = useState<Set<number>>(
    () => {
      return new Set()
    },
  )

  useEffect(() => {
    if (!enabled) {
      return
    }

    let stopped = false
    let socket: WebSocket | null = null
    let attempts = 0

    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let snapshotTimer: ReturnType<typeof setTimeout> | null = null

    const requests = new AbortController()

    function clearSnapshotTimer() {
      if (snapshotTimer !== null) {
        clearTimeout(snapshotTimer)
      }

      snapshotTimer = null
    }

    function clearRetryTimer() {
      if (retryTimer !== null) {
        clearTimeout(retryTimer)
      }

      retryTimer = null
    }

    function markUnknown(nextStatus: PresenceStatus) {
      setOnlineIds(new Set())
      setStatus(nextStatus)
    }

    function scheduleRetry() {
      if (stopped) {
        return
      }

      if (retryTimer !== null) {
        return
      }

      markUnknown('reconnecting')

      const retryDelay = getRetryDelay(attempts)
      attempts += 1

      retryTimer = setTimeout(() => {
        retryTimer = null
        void connect()
      }, retryDelay)
    }

    async function sessionIsValid() {
      try {
        const response = await fetch('/api/v1/auth/me', {
          credentials: 'include',
          cache: 'no-store',
          signal: requests.signal,
        })

        if (stopped) {
          return false
        }

        if (response.status === 401) {
          markUnknown('login-required')
          stopped = true

          return false
        }

        if (!response.ok) {
          scheduleRetry()
          return false
        }

        return true
      } catch {
        if (!stopped) {
          scheduleRetry()
        }

        return false
      }
    }

    function startSnapshotTimeout(
      currentSocket: WebSocket,
      isSynchronized: () => boolean,
    ) {
      snapshotTimer = setTimeout(() => {
        if (stopped) {
          return
        }

        if (socket !== currentSocket) {
          return
        }

        if (isSynchronized()) {
          return
        }

        currentSocket.close()
      }, 30_000)
    }

    async function connect() {
      if (stopped) {
        return
      }

      clearRetryTimer()

      let nextStatus: PresenceStatus = 'reconnecting'

      if (attempts === 0) {
        nextStatus = 'connecting'
      }

      markUnknown(nextStatus)

      const validSession = await sessionIsValid()

      if (!validSession) {
        return
      }

      if (stopped) {
        return
      }

      let currentSocket: WebSocket

      try {
        currentSocket = connectWebSocket()
      } catch {
        scheduleRetry()
        return
      }

      socket = currentSocket

      let synchronized = false

      startSnapshotTimeout(
        currentSocket,
        () => {
          return synchronized
        },
      )

      currentSocket.addEventListener(
        'message',
        (event: MessageEvent<unknown>) => {
          if (stopped) {
            return
          }

          if (socket !== currentSocket) {
            return
          }

          const message = parsePresenceMessage(event.data)

          if (message === null) {
            return
          }

          if (message.type === 'presence_snapshot') {
            synchronized = true
            attempts = 0

            clearSnapshotTimer()

            setOnlineIds(
              new Set(message.data.online_user_ids),
            )

            setStatus('ready')
            return
          }

          if (!synchronized) {
            return
          }

          setOnlineIds((currentIds) => {
            const nextIds = new Set(currentIds)
            const userId = message.data.user_id

            if (message.data.online) {
              nextIds.add(userId)
            } else {
              nextIds.delete(userId)
            }

            return nextIds
          })
        },
      )

      currentSocket.addEventListener(
        'close',
        (event: CloseEvent) => {
          if (stopped) {
            return
          }

          if (socket !== currentSocket) {
            return
          }

          clearSnapshotTimer()
          socket = null

          if (event.code === 1008) {
            markUnknown('login-required')
            stopped = true

            return
          }

          scheduleRetry()
        },
      )

      currentSocket.addEventListener('error', () => {
        // A failed upgrade is followed by close.
        // Reconnection is handled by the close event.
      })
    }

    void connect()

    return () => {
      stopped = true

      requests.abort()
      clearRetryTimer()
      clearSnapshotTimer()

      if (socket !== null) {
        socket.close()
      }

      socket = null
    }
  }, [enabled])

  if (!enabled) {
    return {
      status: 'disabled',
      onlineIds: emptyOnlineIds,
    }
  }

  return {
    status,
    onlineIds,
  }
}