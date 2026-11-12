import type { Top10Entry } from './api.ts'

export function compareTop10ByRank(
  first: Top10Entry,
  second: Top10Entry,
) {
  return first.rank - second.rank
}

export function top10SongTitle(entry: Top10Entry) {
  return entry.song?.title ?? `Song #${entry.song_id}`
}

export function top10SongArtist(entry: Top10Entry) {
  return entry.song?.artist ?? 'Track details unavailable'
}

export function initialsFor(name: string): string {
  const nameParts = name.split(/\s+/)
  const initials: string[] = []

  for (const part of nameParts) {
    if (!part) {
      continue
    }

    initials.push(part[0])

    if (initials.length === 2) {
      break
    }
  }

  const result = initials.join('')

  return result.toUpperCase()
}

export function durationLabel(
  duration?: number | null,
): string {
  if (duration === undefined) {
    return ''
  }

  if (duration === null) {
    return ''
  }

  if (duration <= 0) {
    return ''
  }

  if (Number.isNaN(duration)) {
    return ''
  }

  const millisecondsPerSecond = 1_000
  const secondsPerMinute = 60

  const totalSeconds = Math.floor(
    duration / millisecondsPerSecond,
  )

  const minutes = Math.floor(
    totalSeconds / secondsPerMinute,
  )

  const seconds = totalSeconds % secondsPerMinute
  const secondsLabel = String(seconds).padStart(2, '0')

  return `${minutes}:${secondsLabel}`
}
