import { api } from './api.ts'
import {
  convertFriends,
  getActionRequest,
  type ApiFriend,
  type DirectoryProfile,
  type FriendRequests,
  type RelationshipAction,
} from './friends.ts'

export type RelationshipData = {
  friends: DirectoryProfile[]
  incoming: DirectoryProfile[]
  outgoing: DirectoryProfile[]
}

export type FriendsPageData = RelationshipData & {
  profiles: DirectoryProfile[]
}

export async function fetchRelationshipData(): Promise<RelationshipData> {
  const [friends, requests] = await Promise.all([
    api<ApiFriend[]>('/api/v1/friends'),
    api<FriendRequests>('/api/v1/friends/requests'),
  ])

  return {
    friends: convertFriends(friends),
    incoming: convertFriends(requests.incoming),
    outgoing: convertFriends(requests.outgoing),
  }
}

export async function fetchFriendsPageData(
  currentUserId: number,
): Promise<FriendsPageData> {
  const [relationships, profiles] = await Promise.all([
    fetchRelationshipData(),
    api<DirectoryProfile[]>('/api/v1/profiles'),
  ])

  const otherProfiles = profiles.filter((profile) => {
    return profile.user_id !== currentUserId
  })

  return {
    friends: relationships.friends,
    incoming: relationships.incoming,
    outgoing: relationships.outgoing,
    profiles: otherProfiles,
  }
}

export async function performRelationshipAction(
  userId: number,
  action: RelationshipAction,
) {
  const request = getActionRequest(action, userId)

  return api<{ status: string }>(
    request.path,
    {
      method: request.method,
    },
  )
}