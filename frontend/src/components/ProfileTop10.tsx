import SectionHeading from './SectionHeading.tsx'
import type { Top10Entry } from '../lib/api.ts'
import {
  compareTop10ByRank,
  top10SongArtist,
  top10SongTitle,
} from '../lib/format.ts'

type MemberTop10Props = {
  displayName: string
  entries?: Top10Entry[]
}

type MemberSongRowProps = {
  entry: Top10Entry
}

function MemberSongRow({
  entry,
}: MemberSongRowProps) {
  const rank = String(entry.rank).padStart(2, '0')
  const title = top10SongTitle(entry)
  const artist = top10SongArtist(entry)

  return (
    <div className="song-row">
      <span className="song-rank">
        {rank}
      </span>

      <div className="song-info">
        <strong>{title}</strong>
        <span>{artist}</span>
      </div>
    </div>
  )
}

export default function MemberTop10({
  displayName,
  entries,
}: MemberTop10Props) {
  function renderSongs() {
    if (!entries) {
      return (
        <p className="social-state">
          This Top 10 is private.
        </p>
      )
    }

    if (entries.length === 0) {
      return (
        <p className="social-state">
          This listener has not added songs yet.
        </p>
      )
    }

    const orderedEntries = [...entries]

    orderedEntries.sort(compareTop10ByRank)

    return (
      <div className="song-list">
        {orderedEntries.map((entry) => (
          <MemberSongRow
            key={entry.id}
            entry={entry}
          />
        ))}
      </div>
    )
  }

  return (
    <section className="card top10-card">
      <SectionHeading
        eyebrow="TOP 10"
        title={`${displayName}’s list`}
      />

      {renderSongs()}
    </section>
  )
}
