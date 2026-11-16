import SectionHeading from '../SectionHeading.tsx'
import {
  type DirectoryProfile,
  type RelationshipAction,
  type RelationshipState,
} from '../../lib/friends.ts'
import AddFriendPanel from './AddFriend.tsx'
import { RequestRow } from './FriendRow.tsx'

type FriendRequestsSectionProps = {
  requests: DirectoryProfile[]
  matchingProfiles: DirectoryProfile[]
  loading: boolean
  error: string
  query: string
  addFriendOpen: boolean
  workingUserId: number | null
  getRelationship: (userId: number) => RelationshipState
  onQueryChange: (query: string) => void
  onTogglePanel: () => void
  onClosePanel: () => void
  onAction: (
    userId: number,
    action: RelationshipAction,
  ) => void
}

export default function FriendRequestsSection({
  requests,
  matchingProfiles,
  loading,
  error,
  query,
  addFriendOpen,
  workingUserId,
  getRelationship,
  onQueryChange,
  onTogglePanel,
  onClosePanel,
  onAction,
}: FriendRequestsSectionProps) {
  function renderRequests() {
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

    if (requests.length === 0) {
      return (
        <p className="social-state">
          No incoming requests.
        </p>
      )
    }

    return (
      <div className="friend-list">
        {requests.map((profile) => (
          <RequestRow
            key={profile.user_id}
            profile={profile}
            relationship="received"
            working={workingUserId === profile.user_id}
            onAction={onAction}
          />
        ))}
      </div>
    )
  }

  function renderAddFriendPanel() {
    if (!addFriendOpen) {
      return null
    }

    return (
      <AddFriendPanel
        query={query}
        profiles={matchingProfiles}
        loading={loading}
        error={error}
        workingUserId={workingUserId}
        getRelationship={getRelationship}
        onQueryChange={onQueryChange}
        onClose={onClosePanel}
        onAction={onAction}
      />
    )
  }

  return (
    <section className="card friends-card">
      <SectionHeading
        eyebrow="PENDING"
        title="Friend requests"
      />

      <h3 className="friend-request-heading">
        Incoming ({requests.length})
      </h3>

      {renderRequests()}

      <button
        className="button button-dark add-friend-trigger"
        type="button"
        aria-expanded={addFriendOpen}
        aria-controls="add-friend-panel"
        onClick={onTogglePanel}
      >
        Add a friend
      </button>

      {renderAddFriendPanel()}
    </section>
  )
}