import {
  useEffect,
  useState,
} from 'react'

import {
  ApiError,
  getErrorMessage,
  type User,
} from '../lib/api.ts'
import {
  getActionSuccessMessage,
  getStoredBlockedIds,
  storeBlockedIds,
  type DirectoryProfile,
  type RelationshipAction,
  type RelationshipState,
} from '../lib/friends.ts'
import {
  fetchFriendsPageData,
  fetchRelationshipData,
  performRelationshipAction,
  type RelationshipData,
} from '../lib/friendsApi.ts'

export default function useFriendsPage(
  user: User,
  onWarning: (message: string) => void,
) {
  const [friends, setFriends] = useState<DirectoryProfile[]>([])
  const [incomingRequests, setIncomingRequests] = useState<DirectoryProfile[]>([])
  const [outgoingRequests, setOutgoingRequests] = useState<DirectoryProfile[]>([])
  const [profiles, setProfiles] = useState<DirectoryProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [actionError, setActionError] = useState('')
  const [actionMessage, setActionMessage] = useState('')
  const [workingUserId, setWorkingUserId] = useState<number | null>(null)
  const [addFriendOpen, setAddFriendOpen] = useState(false)

  const [blockedIds, setBlockedIds] = useState<Set<number>>(() => {
    return getStoredBlockedIds(user.id)
  })

  useEffect(() => {
    storeBlockedIds(user.id, blockedIds)
  }, [blockedIds, user.id])

  useEffect(() => {
    let cancelled = false

    async function loadPage() {
      try {
        const pageData = await fetchFriendsPageData(user.id)

        if (cancelled) {
          return
        }

        setFriends(pageData.friends)
        setIncomingRequests(pageData.incoming)
        setOutgoingRequests(pageData.outgoing)
        setProfiles(pageData.profiles)
      } catch (reason) {
        if (cancelled) {
          return
        }

        const message = getErrorMessage(
          reason,
          'Could not load people.',
        )

        setError(message)
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadPage()

    return () => {
      cancelled = true
    }
  }, [user.id])

  function applyRelationshipData(
    relationships: RelationshipData,
  ) {
    setFriends(relationships.friends)
    setIncomingRequests(relationships.incoming)
    setOutgoingRequests(relationships.outgoing)
  }

  async function refreshRelationships() {
    const relationships = await fetchRelationshipData()
    applyRelationshipData(relationships)
  }

  function clearActionMessages() {
    setActionError('')
    setActionMessage('')
  }

  function toggleAddFriendPanel() {
    setAddFriendOpen((currentValue) => {
      return !currentValue
    })

    clearActionMessages()
  }

  function closeAddFriendPanel() {
    setAddFriendOpen(false)
  }

  function changeQuery(nextQuery: string) {
    setQuery(nextQuery)
    clearActionMessages()
  }

  function blockUser(userId: number) {
    setBlockedIds((currentIds) => {
      const nextIds = new Set(currentIds)
      nextIds.add(userId)

      return nextIds
    })
  }

  function unblockUser(userId: number) {
    setBlockedIds((currentIds) => {
      const nextIds = new Set(currentIds)
      nextIds.delete(userId)

      return nextIds
    })
  }

  async function handleRelationshipAction(
    userId: number,
    action: RelationshipAction,
  ) {
    setWorkingUserId(userId)
    clearActionMessages()

    try {
      const result = await performRelationshipAction(
        userId,
        action,
      )

      if (action === 'block') {
        blockUser(userId)
      }

      if (action === 'unblock') {
        unblockUser(userId)
      }

      await refreshRelationships()

      const message = getActionSuccessMessage(
        action,
        result.status,
      )

      setActionMessage(message)

      if (action === 'request') {
        setQuery('')
      }

      if (action === 'accept') {
        setQuery('')
      }
    } catch (reason) {
      if (
        action === 'unblock' &&
        reason instanceof ApiError &&
        reason.status === 404
      ) {
        unblockUser(userId)
        setActionMessage('No active block was found. The saved blocked status was cleared.')
        return
      }

      if (
        action === 'request' &&
        reason instanceof ApiError &&
        reason.status === 404
      ) {
        onWarning(
          'Could not send the request. This person may have blocked you or may no longer be available.',
        )
        return
      }

      const message = getErrorMessage(
        reason,
        'Could not update this relationship.',
      )

      setActionError(message)
    } finally {
      setWorkingUserId(null)
    }
  }

  function getRelationship(
    userId: number,
  ): RelationshipState {
    if (blockedIds.has(userId)) {
      return 'blocked'
    }

    const isFriend = friends.some((profile) => {
      return profile.user_id === userId
    })

    if (isFriend) {
      return 'friend'
    }

    const requestWasReceived = incomingRequests.some((profile) => {
      return profile.user_id === userId
    })

    if (requestWasReceived) {
      return 'received'
    }

    const requestWasSent = outgoingRequests.some((profile) => {
      return profile.user_id === userId
    })

    if (requestWasSent) {
      return 'sent'
    }

    return 'none'
  }

  const normalizedQuery = query
    .trim()
    .toLocaleLowerCase()

  const matchingProfiles = profiles.filter((profile) => {
    const displayName = profile.display_name.toLocaleLowerCase()

    return displayName.includes(normalizedQuery)
  })

  return {
    friends,
    incomingRequests,
    matchingProfiles,
    loading,
    error,
    query,
    actionError,
    actionMessage,
    workingUserId,
    addFriendOpen,
    getRelationship,
    changeQuery,
    toggleAddFriendPanel,
    closeAddFriendPanel,
    handleRelationshipAction,
  }
}
