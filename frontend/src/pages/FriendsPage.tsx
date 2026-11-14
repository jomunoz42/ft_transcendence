import FriendsListSection from '../components/friends/FriendList.tsx'
import FriendRequestsSection from '../components/friends/FriendRequest.tsx'
import useFriendsPage from '../hooks/useFriendsPage.ts'
import type { User } from '../lib/api.ts'
import type { Presence } from '../lib/friends.ts'

type FriendsPageProps = {
  user: User
  presence: Presence
  onWarning: (message: string) => void
}

export default function FriendsPage({
  user,
  presence,
  onWarning,
}: FriendsPageProps) {
  const friendsPage = useFriendsPage(user, onWarning)

  function renderActionMessage() {
    if (friendsPage.actionError) {
      return (
        <p
          className="form-error"
          role="alert"
        >
          {friendsPage.actionError}
        </p>
      )
    }

    if (friendsPage.actionMessage) {
      return (
        <p
          className="form-note"
          role="status"
        >
          {friendsPage.actionMessage}
        </p>
      )
    }

    return null
  }

  return (
    <div className="friends-page-content">
      {renderActionMessage()}

      <FriendsListSection
        friends={friendsPage.friends}
        presence={presence}
        loading={friendsPage.loading}
        error={friendsPage.error}
        workingUserId={friendsPage.workingUserId}
        onAction={friendsPage.handleRelationshipAction}
      />

      <FriendRequestsSection
        requests={friendsPage.incomingRequests}
        matchingProfiles={friendsPage.matchingProfiles}
        loading={friendsPage.loading}
        error={friendsPage.error}
        query={friendsPage.query}
        addFriendOpen={friendsPage.addFriendOpen}
        workingUserId={friendsPage.workingUserId}
        getRelationship={friendsPage.getRelationship}
        onQueryChange={friendsPage.changeQuery}
        onTogglePanel={friendsPage.toggleAddFriendPanel}
        onClosePanel={friendsPage.closeAddFriendPanel}
        onAction={friendsPage.handleRelationshipAction}
      />
    </div>
  )
}
