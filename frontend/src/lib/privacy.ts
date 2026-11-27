import { ApiError } from './api.ts'

export type DeletionRequest = {
  detail: string
  expires_at: string
  cooldown_seconds: number
}

function exportFilename(header: string | null) {
  const match = header?.match(/(?:^|;)\s*filename="?([A-Za-z0-9._-]+\.json)"?(?:;|$)/i)
  return match?.[1] ?? 'myplaylist-data.json'
}

export async function downloadPrivacyExport(): Promise<'sent' | 'failed'> {
  const response = await fetch('/api/v1/privacy/export', {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
  })

  if (!response.ok) {
    let detail: unknown
    try {
      const body: unknown = await response.json()
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        detail = body.detail
      }
    } catch {
    }
    throw new ApiError(response.status, detail)
  }

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  try {
    link.href = objectUrl
    link.download = exportFilename(response.headers.get('Content-Disposition'))
    link.style.display = 'none'
    document.body.append(link)
    link.click()
  } finally {
    link.remove()
    URL.revokeObjectURL(objectUrl)
  }

  return response.headers.get('X-Confirmation-Email') === 'failed' ? 'failed' : 'sent'
}
