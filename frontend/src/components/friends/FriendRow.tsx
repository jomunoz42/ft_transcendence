import Link from '../Link.tsx'
import { initialsFor } from '../../lib/format.ts'
import {
  getRelationshipLabel,
  type DirectoryProfile,
  type Presence,
  type RelationshipAction,
  type RelationshipState,
} from '../../lib/friends.ts'
import FriendActions from './FriendActions.tsx'

type RowAction = (
  userId: number,
  action: RelationshipAction,
) => void

type FriendRowProps = {
  profile: DirectoryProfile
  presence: Presence
  relationship: RelationshipState
  working: boolean
  onAction: RowAction
}

type RequestRowProps = {
  profile: DirectoryProfile
  relationship: RelationshipState
  working: boolean
  onAction: RowAction
}

function getPresenceLabel(
  userId: number,
  presence: Presence,
) {
  if (presence.status === 'ready') {
    if (presence.onlineIds.has(userId)) {
      return 'Online'
    }

    return 'Offline'
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

  return 'Offline'
}

function getPresenceClassName(
  userId: number,
  presence: Presence,
) {
  const classNames = ['presence']

  if (presence.status === 'ready') {
    if (presence.onlineIds.has(userId)) {
      classNames.push('is-online')
    } else {
      classNames.push('is-offline')
    }
  }

  if (presence.status === 'login-required') {
    classNames.push('is-offline')
  }

  if (presence.status === 'reconnecting') {
    classNames.push('is-reconnecting')
  }

  return classNames.join(' ')
}

export function FriendRow({
  profile,
  presence,
  relationship,
  working,
  onAction,
}: FriendRowProps) {
  let bio = 'No bio added yet.'

  if (profile.bio) {
    bio = profile.bio
  }

  const profilePath = `/members/${profile.user_id}` as const
  const presenceLabel = getPresenceLabel(
    profile.user_id,
    presence,
  )

  const presenceClassName = getPresenceClassName(
    profile.user_id,
    presence,
  )

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

        <small className="relationship-state">
          {getRelationshipLabel(relationship)}
        </small>
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

        <FriendActions
          profile={profile}
          relationship={relationship}
          working={working}
          onAction={onAction}
        />
      </div>
    </div>
  )
}

export function RequestRow({
  profile,
  relationship,
  working,
  onAction,
}: RequestRowProps) {
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

        <small className="relationship-state">
          {getRelationshipLabel(relationship)}
        </small>
      </div>

      <div className="friend-row-actions">
        <Link
          to={profilePath}
          className="button button-outline friend-view"
        >
          View profile
          {' '}
          <span>→</span>
        </Link>

        <FriendActions
          profile={profile}
          relationship={relationship}
          working={working}
          onAction={onAction}
        />
      </div>
    </div>
  )
}