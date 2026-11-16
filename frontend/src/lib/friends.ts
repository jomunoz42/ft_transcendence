import type { PresenceStatus } from '../websocket/useWebSocket.ts'

export type DirectoryProfile = {
  user_id: number
  display_name: string
  bio?: string | null
}

export type ApiFriend = {
  id: number
  display_name: string
}

export type FriendRequests = {
  incoming: ApiFriend[]
  outgoing: ApiFriend[]
}

export type RelationshipState =
  | 'friend'
  | 'sent'
  | 'received'
  | 'none'
  | 'blocked'

export type RelationshipAction =
  | 'request'
  | 'accept'
  | 'decline'
  | 'cancel'
  | 'remove'
  | 'block'
  | 'unblock'

export type Presence = {
  status: PresenceStatus
  onlineIds: Set<number>
}

type ActionRequest = {
  path: string
  method: 'POST' | 'DELETE'
}

export function convertFriends(
  friends: ApiFriend[],
): DirectoryProfile[] {
  return friends.map((friend) => {
    return {
      user_id: friend.id,
      display_name: friend.display_name,
      bio: null,
    }
  })
}

export function getStoredBlockedIds(userId: number) {
  try {
    const storageKey = `myplaylist-blocked-users-${userId}`
    const storedValue = window.localStorage.getItem(storageKey)

    if (!storedValue) {
      return new Set<number>()
    }

    const parsedValue: unknown = JSON.parse(storedValue)

    if (!Array.isArray(parsedValue)) {
      return new Set<number>()
    }

    const blockedIds = new Set<number>()

    for (const value of parsedValue) {
      if (typeof value !== 'number') {
        continue
      }

      if (!Number.isSafeInteger(value)) {
        continue
      }

      if (value <= 0) {
        continue
      }

      blockedIds.add(value)
    }

    return blockedIds
  } catch {
    return new Set<number>()
  }
}

export function storeBlockedIds(
  userId: number,
  blockedIds: Set<number>,
) {
  const storageKey = `myplaylist-blocked-users-${userId}`
  const storedValue = JSON.stringify(Array.from(blockedIds))

  window.localStorage.setItem(storageKey, storedValue)
}

export function getRelationshipLabel(
  relationship: RelationshipState,
) {
  if (relationship === 'friend') {
    return 'Friend'
  }

  if (relationship === 'sent') {
    return 'Request sent'
  }

  if (relationship === 'received') {
    return 'Request received'
  }

  if (relationship === 'blocked') {
    return 'Blocked'
  }

  return 'No relationship'
}

export function getRelationshipActions(
  relationship: RelationshipState,
): RelationshipAction[] {
  if (relationship === 'friend') {
    return ['remove', 'block']
  }

  if (relationship === 'sent') {
    return ['cancel', 'block']
  }

  if (relationship === 'received') {
    return ['accept', 'decline', 'block']
  }

  if (relationship === 'blocked') {
    return ['unblock']
  }

  return ['request', 'block']
}

export function getActionLabel(
  action: RelationshipAction,
) {
  if (action === 'request') {
    return 'Add friend'
  }

  if (action === 'accept') {
    return 'Accept'
  }

  if (action === 'decline') {
    return 'Decline'
  }

  if (action === 'cancel') {
    return 'Cancel request'
  }

  if (action === 'remove') {
    return 'Remove friend'
  }

  if (action === 'block') {
    return 'Block'
  }

  return 'Unblock'
}

export function getActionClassName(
  action: RelationshipAction,
) {
  if (action === 'request') {
    return 'button button-dark relationship-action'
  }

  if (action === 'accept') {
    return 'button button-dark relationship-action'
  }

  if (action === 'unblock') {
    return 'button button-dark relationship-action'
  }

  if (action === 'block') {
    return 'button button-outline relationship-action relationship-action-danger'
  }

  if (action === 'remove') {
    return 'button button-outline relationship-action relationship-action-danger'
  }

  if (action === 'decline') {
    return 'button button-outline relationship-action relationship-action-danger'
  }

  return 'button button-outline relationship-action'
}

export function getActionRequest(
  action: RelationshipAction,
  userId: number,
): ActionRequest {
  if (action === 'request') {
    return {
      path: `/api/v1/friends/request/${userId}`,
      method: 'POST',
    }
  }

  if (action === 'accept') {
    return {
      path: `/api/v1/friends/accept/${userId}`,
      method: 'POST',
    }
  }

  if (action === 'decline') {
    return {
      path: `/api/v1/friends/decline/${userId}`,
      method: 'POST',
    }
  }

  if (action === 'cancel') {
    return {
      path: `/api/v1/friends/cancel/${userId}`,
      method: 'POST',
    }
  }

  if (action === 'remove') {
    return {
      path: `/api/v1/friends/${userId}`,
      method: 'DELETE',
    }
  }

  if (action === 'block') {
    return {
      path: `/api/v1/friends/block/${userId}`,
      method: 'POST',
    }
  }

  return {
    path: `/api/v1/friends/unblock/${userId}`,
    method: 'POST',
  }
}

export function getActionSuccessMessage(
  action: RelationshipAction,
  responseStatus: string,
) {
  if (action === 'request') {
    if (responseStatus === 'accepted') {
      return 'You are now friends.'
    }

    return 'Friend request sent.'
  }

  if (action === 'accept') {
    return 'Friend request accepted.'
  }

  if (action === 'decline') {
    return 'Friend request declined.'
  }

  if (action === 'cancel') {
    return 'Friend request cancelled.'
  }

  if (action === 'remove') {
    return 'Friend removed.'
  }

  if (action === 'block') {
    return 'User blocked.'
  }

  return 'User unblocked.'
}