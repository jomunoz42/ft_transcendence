import type { ProfileData, User } from '../lib/api.ts'
import { initialsFor } from '../lib/format.ts'
import type { PresenceStatus } from '../websocket/useWebSocket.ts'

type ProfileCardProps = {
  user: User
  profile: ProfileData | null
  presenceStatus: PresenceStatus
}

function getPresenceText(status: PresenceStatus) {
  if (status === 'ready') {
    return 'Online'
  }

  if (status === 'reconnecting') {
    return 'Reconnecting'
  }

  if (status === 'connecting') {
    return 'Connecting'
  }

  return 'Offline'
}

export default function ProfileCard({
  user,
  profile,
  presenceStatus,
}: ProfileCardProps) {
  const displayName = user.display_name
  const initials = initialsFor(displayName)
  const presenceText = getPresenceText(presenceStatus)

  let presenceClassName = 'online-dot'

  if (presenceStatus !== 'ready') {
    presenceClassName += ' is-unknown'
  }

  let favouriteSongs: number | string = '—'

  if (profile?.top10_entries) {
    favouriteSongs = profile.top10_entries.length
  }

  return (
    <section className="card profile-card">
      <div className="profile-card-top">
        <span className="avatar avatar-large">
          {initials}
        </span>

        <span
          className={presenceClassName}
          title={presenceText}
          role="img"
          aria-label={presenceText}
        />
      </div>

      <span className="eyebrow">
        YOUR PROFILE
      </span>

      <h3>{displayName}</h3>

      <p>
        Collecting songs for every version of me.
      </p>

      <div className="profile-stats">
        <div>
          <strong>{favouriteSongs}</strong>
          <span>favourite songs</span>
        </div>

        <div>
          <strong>—</strong>
          <span>friends</span>
        </div>
      </div>
    </section>
  )
}