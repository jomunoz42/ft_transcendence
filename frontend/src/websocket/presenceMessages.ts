export type PresenceMessage =
  | {
      type: 'presence_snapshot'
      data: {
        online_user_ids: number[]
      }
    }
  | {
      type: 'presence'
      data: {
        user_id: number
        online: boolean
      }
    }

function isObject(
  value: unknown,
): value is Record<string, unknown> {
  if (typeof value !== 'object') {
    return false
  }

  if (value === null) {
    return false
  }

  return true
}

function isValidUserId(
  value: unknown,
): value is number {
  if (typeof value !== 'number') {
    return false
  }

  if (!Number.isSafeInteger(value)) {
    return false
  }

  if (value <= 0) {
    return false
  }

  return true
}

function parseOnlineIds(
  value: unknown,
): number[] | null {
  if (!Array.isArray(value)) {
    return null
  }

  const onlineIds: number[] = []

  for (const userId of value) {
    if (!isValidUserId(userId)) {
      return null
    }

    onlineIds.push(userId)
  }

  return onlineIds
}

function parseSnapshot(
  data: Record<string, unknown>,
): PresenceMessage | null {
  const onlineIds = parseOnlineIds(
    data.online_user_ids,
  )

  if (onlineIds === null) {
    return null
  }

  return {
    type: 'presence_snapshot',
    data: {
      online_user_ids: onlineIds,
    },
  }
}

function parsePresenceUpdate(
  data: Record<string, unknown>,
): PresenceMessage | null {
  const userId = data.user_id
  const online = data.online

  if (!isValidUserId(userId)) {
    return null
  }

  if (typeof online !== 'boolean') {
    return null
  }

  return {
    type: 'presence',
    data: {
      user_id: userId,
      online,
    },
  }
}

export function parsePresenceMessage(
  value: unknown,
): PresenceMessage | null {
  if (typeof value !== 'string') {
    return null
  }

  let parsedValue: unknown

  try {
    parsedValue = JSON.parse(value)
  } catch {
    return null
  }

  if (!isObject(parsedValue)) {
    return null
  }

  if (typeof parsedValue.type !== 'string') {
    return null
  }

  if (!isObject(parsedValue.data)) {
    return null
  }

  if (parsedValue.type === 'presence_snapshot') {
    return parseSnapshot(parsedValue.data)
  }

  if (parsedValue.type === 'presence') {
    return parsePresenceUpdate(parsedValue.data)
  }

  return null
}