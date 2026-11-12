import type { CSSProperties } from 'react'

import type { Top10Entry } from '../lib/api.ts'
import {
  compareTop10ByRank,
  durationLabel,
  top10SongArtist,
  top10SongTitle,
} from '../lib/format.ts'

const songColors = [
  'amber',
  'rose',
  'blue',
  'violet',
  'green',
]

type SongRowsProps = {
  entries: Top10Entry[]
}

type SongRowProps = {
  entry: Top10Entry
  color: string
}

function SongRow({
  entry,
  color,
}: SongRowProps) {
  const song = entry.song

  const title = top10SongTitle(entry)
  let details = top10SongArtist(entry)
  let coverStyle: CSSProperties | undefined
  let durationMilliseconds: number | null | undefined

  if (song) {
    if (song.album) {
      details += ` · ${song.album}`
    }

    if (song.cover_url) {
      coverStyle = {
        backgroundImage: `url(${song.cover_url})`,
        backgroundSize: 'cover',
      }
    }

    durationMilliseconds = song.duration_ms
  }

  return (
    <div className="song-row">
      <span className="song-rank">
        {String(entry.rank).padStart(2, '0')}
      </span>

      <span
        className={`album-art ${color}`}
        aria-hidden="true"
        style={coverStyle}
      >
        ♫
      </span>

      <div className="song-info">
        <strong>{title}</strong>
        <span>{details}</span>
      </div>

      <span className="duration">
        {durationLabel(durationMilliseconds)}
      </span>
    </div>
  )
}

export default function SongRows({
  entries,
}: SongRowsProps) {
  const sortedEntries = [...entries]

  sortedEntries.sort(compareTop10ByRank)

  function renderEntry(entry: Top10Entry, index: number) {
    const colorIndex = index % songColors.length
    const color = songColors[colorIndex]
    return (
      <SongRow
        key={entry.id}
        entry={entry}
        color={color}
      />
    )
  }

  return (
    <div className="song-list">
      {sortedEntries.map(renderEntry)}
    </div>
  )
}
