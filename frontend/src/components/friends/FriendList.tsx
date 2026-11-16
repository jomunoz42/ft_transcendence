import SectionHeading from '../SectionHeading.tsx'
import {
  type DirectoryProfile,
  type Presence,
  type RelationshipAction,
} from '../../lib/friends.ts'
import { FriendRow } from './FriendRow.tsx'

type FriendsListSectionProps = {
  friends: DirectoryProfile[]
  presence: Presence
  loading: boolean
  error: string
  workingUserId: number | null
  onAction: (
    userId: number,
    action: RelationshipAction,
  ) => void
}

export default function FriendsListSection({
  friends,
  presence,
  loading,
  error,
  workingUserId,
  onAction,
}: FriendsListSectionProps) {
  function renderFriends() {
    if (loading) {
      return (
        <p className="social-state">
          Loading…
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

    if (friends.length === 0) {
      return (
        <p className="social-state">
          You have not added any friends yet.
        </p>
      )
    }

    return (
      <div className="friend-list">
        {friends.map((profile) => (
          <FriendRow
            key={profile.user_id}
            profile={profile}
            presence={presence}
            relationship="friend"
            working={workingUserId === profile.user_id}
            onAction={onAction}
          />
        ))}
      </div>
    )
  }

  return (
    <section className="card friends-card">
      <SectionHeading
        eyebrow="YOUR CIRCLE"
        title={`Friends (${friends.length})`}
      />

      {renderFriends()}
    </section>
  )
}