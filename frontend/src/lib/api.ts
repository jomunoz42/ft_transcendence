export type User = {
  id: number
  display_name: string
}

export type Song = {
  title?: string
  artist?: string
  album?: string | null
  cover_url?: string | null
  duration_ms?: number | null
}

export type Top10Entry = {
  id: number
  rank: number
  song_id: number
  song?: Song
}

export type ProfileComment = {
  id: number
  author_id: number
  body: string
}

export type ProfileData = {
  display_name: string
  bio?: string | null
  is_top10_public?: boolean
  top10_entries?: Top10Entry[]
  comments?: ProfileComment[]
}

type ValidationError = {
  loc?: unknown[]
  msg?: unknown
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    const message = apiErrorMessage(status, detail)

    super(message)

    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function getErrorMessage(
  reason: unknown,
  defaultMessage: string,
) {
  if (reason instanceof Error) {
    return reason.message
  }

  return defaultMessage
}

function isObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== 'object') {
    return false
  }

  if (value === null) {
    return false
  }

  return true
}

function isNonEmptyString(value: unknown): value is string {
  if (typeof value !== 'string') {
    return false
  }

  if (!value.trim()) {
    return false
  }

  return true
}

function getValidationMessage(detail: unknown[]) {
  const messages: string[] = []

  for (const item of detail) {
    if (!isObject(item)) {
      continue
    }

    const error = item as ValidationError

    if (typeof error.msg !== 'string') {
      continue
    }

    let message = error.msg

    if (Array.isArray(error.loc)) {
      const field = error.loc.at(-1)

      if (typeof field === 'string') {
        message = `${field}: ${error.msg}`
      }
    }

    messages.push(message)
  }

  if (messages.length === 0) {
    return null
  }

  return messages.join(' ')
}

function getObjectMessage(detail: unknown) {
  if (!isObject(detail)) {
    return null
  }

  const message = detail.message

  if (!isNonEmptyString(message)) {
    return null
  }

  return message
}

function apiErrorMessage(status: number, detail: unknown) {
  if (isNonEmptyString(detail)) {
    return detail
  }

  if (Array.isArray(detail)) {
    const validationMessage = getValidationMessage(detail)

    if (validationMessage !== null) {
      return validationMessage
    }
  }

  const objectMessage = getObjectMessage(detail)

  if (objectMessage !== null) {
    return objectMessage
  }

  return (
    `The server returned an error (HTTP ${status}). ` +
    'Check that the backend is running.'
  )
}

async function readErrorDetail(response: Response) {
  let body: unknown

  try {
    body = await response.json()
  } catch {
    return undefined
  }

  if (!isObject(body)) {
    return undefined
  }

  return body.detail
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)

  if (init.body) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    const detail = await readErrorDetail(response)

    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  const body = await response.json()

  return body as T
}
