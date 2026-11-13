import { initialsFor } from '../../lib/format.ts'
import {
  getRelationshipLabel,
  type DirectoryProfile,
  type RelationshipAction,
  type RelationshipState,
} from '../../lib/friends.ts'
import FriendAction from './FriendActions.tsx'

type AddFriendPanelProps = {
  query: string
  profiles: DirectoryProfile[]
  loading: boolean
  error: string
  workingUserId: number | null
  getRelationship: (userId: number) => RelationshipState
  onQueryChange: (query: string) => void
  onClose: () => void
  onAction: (
    userId: number,
    action: RelationshipAction,
  ) => void
}

export default function AddFriendPanel({
  query,
  profiles,
  loading,
  error,
  workingUserId,
  getRelationship,
  onQueryChange,
  onClose,
  onAction,
}: AddFriendPanelProps) {
  function renderResults() {
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

    if (!query.trim()) {
      return null
    }

    if (profiles.length === 0) {
      return (
        <p className="social-state">
          No people match that name.
        </p>
      )
    }

    return (
      <div className="friend-list">
        {profiles.map((profile) => {
          const relationship = getRelationship(
            profile.user_id,
          )

          const working =
            workingUserId === profile.user_id

          return (
            <div
              className="friend-row"
              key={profile.user_id}
            >
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

              <FriendAction
                profile={profile}
                relationship={relationship}
                working={working}
                onAction={onAction}
              />
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <section
      className="add-friend-panel"
      id="add-friend-panel"
      aria-label="Add a friend"
    >
      <div className="add-friend-panel-heading">
        <h3>Find someone by name</h3>

        <button
          className="text-button"
          type="button"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      <label className="friend-search">
        Search by name

        <input
          type="search"
          value={query}
          placeholder="Type a display name"
          aria-label="Search people to add by name"
          onChange={(event) => {
            onQueryChange(event.target.value)
          }}
        />
      </label>

      {renderResults()}
    </section>
  )
}