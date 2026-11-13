import {
  useEffect,
  useState,
} from 'react'

import Link from '../components/Link.tsx'
import SectionHeading from '../components/SectionHeading.tsx'
import {
  api,
  getErrorMessage,
  type User,
} from '../lib/api.ts'
import { initialsFor } from '../lib/format.ts'
import type { PresenceStatus } from '../websocket/useWebSocket.ts'

type DirectoryProfile = {
  user_id: number
  display_name: string
  bio: string | null
}

type Presence = {
  status: PresenceStatus
  onlineIds: Set<number>
}

type FriendsPageProps = {
  user: User
  presence: Presence
}

type FriendRowProps = {
  profile: DirectoryProfile
  presence: Presence
}

function getPresenceLabel(
  userId: number,
  presence: Presence,
) {
  if (presence.status === 'ready') {
    if (presence.onlineIds.has(userId)) {
      return 'Online'
    }

    return 'Unknown'
  }

  if (presence.status === 'reconnecting') {
    return 'Reconnecting…'
  }

  if (presence.status === 'connecting') {
    return 'Connecting…'
  }

  if (presence.status === 'login-required') {
    return 'Sign in again'
  }

  return 'Unknown'
}

function getPresenceClassName(
  userId: number,
  presence: Presence,
) {
  const classNames = ['presence']

  const isOnline =
    presence.status === 'ready' &&
    presence.onlineIds.has(userId)

  if (isOnline) {
    classNames.push('is-online')
  } else {
    classNames.push('is-unknown')
  }

  if (presence.status === 'reconnecting') {
    classNames.push('is-reconnecting')
  }

  return classNames.join(' ')
}

function FriendRow({
  profile,
  presence,
}: FriendRowProps) {
  let bio = profile.bio

  if (!bio) {
    bio = 'No bio added yet.'
  }

  const presenceLabel = getPresenceLabel(
    profile.user_id,
    presence,
  )

  const presenceClassName = getPresenceClassName(
    profile.user_id,
    presence,
  )

  const profilePath = `/members/${profile.user_id}` as const

  return (
    <div className="friend-row">
      <span
        className="avatar"
        aria-hidden="true"
      >
        {initialsFor(profile.display_name)}
      </span>

      <div className="friend-details">
        <strong>{profile.display_name}</strong>
        <span>{bio}</span>
      </div>

      <span className={presenceClassName}>
        <i />
        {' '}
        {presenceLabel}
      </span>

      <div className="friend-row-actions">
        <Link
          to={profilePath}
          className="button button-outline friend-view"
        >
          View profile
          {' '}
          <span>→</span>
        </Link>
      </div>
    </div>
  )
}

export default function FriendsPage({
  user,
  presence,
}: FriendsPageProps) {
  const [profiles, setProfiles] = useState<DirectoryProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadProfiles() {
      try {
        const results = await api<DirectoryProfile[]>(
          '/api/v1/profiles',
        )

        if (cancelled) {
          return
        }

        const otherProfiles = results.filter((profile) => {
          return profile.user_id !== user.id
        })

        setProfiles(otherProfiles)
      } catch (reason) {
        if (cancelled) {
          return
        }

        setError(getErrorMessage(reason, 'Could not load people.'))
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadProfiles()

    return () => {
      cancelled = true
    }
  }, [user])

  const normalizedQuery = query
    .trim()
    .toLocaleLowerCase()

  const matchingProfiles = profiles.filter((profile) => {
    const displayName = profile.display_name.toLocaleLowerCase()

    return displayName.includes(normalizedQuery)
  })

  function renderProfiles() {
    if (loading) {
      return (
        <p className="social-state">
          Loading people…
        </p>
      )
    }

    if (error) {
      return (
        <p
          className="social-state"
          role="alert"
        >
          {error}
        </p>
      )
    }

    if (matchingProfiles.length === 0) {
      let message = 'No other listeners yet.'

      if (query.trim()) {
        message = 'No listeners match that name.'
      }

      return (
        <p className="social-state">
          {message}
        </p>
      )
    }

    return (
      <div className="friend-list">
        {matchingProfiles.map((profile) => (
          <FriendRow
            key={profile.user_id}
            profile={profile}
            presence={presence}
          />
        ))}
      </div>
    )
  }

  return (
    <section className="card friends-card">
      <SectionHeading
        eyebrow="COMMUNITY"
        title="Find listeners"
      />

      <label className="friend-search">
        Search by name

        <input
          type="search"
          value={query}
          placeholder="Type a display name"
          aria-label="Search listeners by name"
          onChange={(event) => {
            setQuery(event.target.value)
          }}
        />
      </label>

      {renderProfiles()}
    </section>
  )
}
