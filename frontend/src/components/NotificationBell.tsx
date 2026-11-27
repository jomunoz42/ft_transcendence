import {
  useEffect,
  useId,
  useRef,
  useState,
  type UIEvent,
} from 'react'

import bellIcon from '../assets/icons/bellIcon.svg'
import useNotifications from '../hooks/useNotifications.ts'
import type { PresenceStatus } from '../websocket/useWebSocket.ts'

type NotificationBellProps = {
  revision: number
  connectionStatus: PresenceStatus
  onSessionExpired: () => void
}

function timestamp(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Time unavailable'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export default function NotificationBell({ revision, connectionStatus, onSessionExpired }: NotificationBellProps) {
  const notifications = useNotifications(revision, onSessionExpired)
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const bell = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLElement>(null)
  const lastReadButton = useRef<HTMLButtonElement | null>(null)
  const panelId = useId()
  const titleId = useId()
  const { unreadCount, loading, loadingMore, readingId, error, actionError, items } = notifications
  const busy = loading || loadingMore || readingId !== null
  const label = unreadCount === null ? 'Notifications, unread count unavailable' : `Notifications, ${unreadCount} unread`

  function loadOlderOnScroll(event: UIEvent<HTMLElement>) {
    const container = event.currentTarget
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight

    if (distanceFromBottom <= 48 && notifications.hasOlder && !busy) {
      notifications.older()
    }
  }

  useEffect(() => {
    if (readingId === null && !loading && !loadingMore && lastReadButton.current) {
      // The successful read removes its button. Keep keyboard users in the
      // panel unless they have already moved focus somewhere else.
      if (document.activeElement === document.body) {
        if (lastReadButton.current.isConnected) lastReadButton.current.focus()
        else panel.current?.focus()
      }
      lastReadButton.current = null
    }
  }, [items, readingId, loading, loadingMore])

  useEffect(() => {
    if (!open) return
    function dismiss(event: PointerEvent | KeyboardEvent) {
      if (event instanceof KeyboardEvent) {
        if (event.key === 'Escape') {
          setOpen(false)
          bell.current?.focus()
        }
      } else if (event.target instanceof Node && !root.current?.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('keydown', dismiss)
    return () => {
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('keydown', dismiss)
    }
  }, [open])

  return (
    <div className="notification-center" ref={root} onBlur={(event) => {
      if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) setOpen(false)
    }}>
      <button ref={bell} type="button" className="notification-bell" aria-label={label}
        aria-expanded={open} aria-controls={panelId} title="Notifications"
        onClick={() => {
          if (!open) notifications.newest()
          setOpen(!open)
        }}>
        <img src={bellIcon} alt="" aria-hidden="true" />
        {unreadCount !== null && unreadCount > 0 && <span className="notification-badge" aria-hidden="true">{unreadCount > 99 ? '99+' : unreadCount}</span>}
        {error && <span className="notification-badge" aria-hidden="true">!</span>}
      </button>
      <span className="sr-only" role="status">{unreadCount !== null ? `${unreadCount} unread notifications` : ''}</span>

      {open && (
        <section ref={panel} id={panelId} className="notification-panel" aria-labelledby={titleId}
          tabIndex={-1} onScroll={loadOlderOnScroll}>
          <div className="notification-heading">
            <h2 id={titleId}>Notifications</h2>
          </div>
          <div className="notification-toolbar">
            <span>{unreadCount === null ? 'Unread count unavailable' : `${unreadCount} unread`}</span>
            <button type="button" className="text-button" onClick={notifications.refresh} disabled={busy}>Refresh</button>
          </div>
          {connectionStatus === 'reconnecting' && <p className="notification-state">Live updates are reconnecting. You can still refresh saved notifications.</p>}
          {loading && <p className="notification-state" role="status">Loading notifications…</p>}
          {error && <div className="notification-error" role="alert">
            <p>{error}</p>
            <button type="button" className="button button-outline" onClick={notifications.refresh} disabled={busy}>Try again</button>
          </div>}
          {actionError && <p className="notification-error" role="alert">{actionError}</p>}
          {!loading && !error && items.length === 0 && <p className="notification-state">No notifications yet.</p>}
          <ul className="notification-list" aria-label="Recent notifications" aria-busy={loading || loadingMore}>
            {items.map((item) => (
              <li key={item.id} className={`notification-item${item.read_at === null ? ' notification-unread' : ''}`}>
                <p className="notification-message">{item.message}</p>
                <div className="notification-meta">
                  <time dateTime={item.created_at}>{timestamp(item.created_at)}</time>
                  <span>{item.read_at === null ? 'Unread' : 'Read'}</span>
                </div>
                {item.read_at === null && <button type="button" className="text-button" disabled={busy}
                  onClick={(event) => {
                    lastReadButton.current = event.currentTarget
                    void notifications.markRead(item.id)
                  }}
                  aria-label={`Mark as read: ${item.message}`}>
                  {readingId === item.id ? 'Marking as read…' : 'Mark as read'}
                </button>}
              </li>
            ))}
          </ul>
          {loadingMore && <p className="notification-state" role="status">Loading older notifications…</p>}
        </section>
      )}
    </div>
  )
}
