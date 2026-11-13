import type { FormEvent } from 'react'

export type SongDraft = {
  title: string
  artist: string
}

type Top10EditorProps = {
  draft: SongDraft[]
  saving: boolean
  message: string
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onTitleChange: (index: number, title: string) => void
  onArtistChange: (index: number, artist: string) => void
  onMoveSong: (index: number, direction: -1 | 1) => void
  onRemoveSong: (index: number) => void
  onAddSong: () => void
}

type SongEditorRowProps = {
  song: SongDraft
  index: number
  totalSongs: number
  onTitleChange: (index: number, title: string) => void
  onArtistChange: (index: number, artist: string) => void
  onMoveSong: (index: number, direction: -1 | 1) => void
  onRemoveSong: (index: number) => void
}

function SongEditorRow({
  song,
  index,
  totalSongs,
  onTitleChange,
  onArtistChange,
  onMoveSong,
  onRemoveSong,
}: SongEditorRowProps) {
  const rank = String(index + 1).padStart(2, '0')
  const isFirstSong = index === 0
  const isLastSong = index === totalSongs - 1

  return (
    <div className="top10-edit-row">
      <span className="song-rank">
        {rank}
      </span>

      <label>
        <span className="sr-only">
          Song title
        </span>

        <input
          value={song.title}
          required
          placeholder="Song title"
          onChange={(event) => {
            onTitleChange(index, event.target.value)
          }}
        />
      </label>

      <label>
        <span className="sr-only">
          Artist
        </span>

        <input
          value={song.artist}
          required
          placeholder="Artist"
          onChange={(event) => {
            onArtistChange(index, event.target.value)
          }}
        />
      </label>

      <div className="editor-row-actions">
        <button
          type="button"
          className="editor-icon-button"
          aria-label="Move song up"
          disabled={isFirstSong}
          onClick={() => {
            onMoveSong(index, -1)
          }}
        >
          ↑
        </button>

        <button
          type="button"
          className="editor-icon-button"
          aria-label="Move song down"
          disabled={isLastSong}
          onClick={() => {
            onMoveSong(index, 1)
          }}
        >
          ↓
        </button>

        <button
          type="button"
          className="editor-icon-button remove-song"
          aria-label="Remove song"
          onClick={() => {
            onRemoveSong(index)
          }}
        >
          ×
        </button>
      </div>
    </div>
  )
}

export default function Top10Editor({
  draft,
  saving,
  message,
  onSubmit,
  onTitleChange,
  onArtistChange,
  onMoveSong,
  onRemoveSong,
  onAddSong,
}: Top10EditorProps) {
  let saveButtonLabel = 'Save Top 10'

  if (saving) {
    saveButtonLabel = 'Saving…'
  }

  function renderAddSongButton() {
    if (draft.length >= 10) {
      return null
    }

    return (
      <button
        type="button"
        className="add-song"
        onClick={onAddSong}
      >
        ＋ <span>Add a song</span>
      </button>
    )
  }

  function renderMessage() {
    if (!message) {
      return null
    }

    return (
      <span
        className="social-state"
        role="status"
      >
        {message}
      </span>
    )
  }

  return (
    <form
      className="top10-editor"
      onSubmit={onSubmit}
    >
      <p className="editor-hint">
        Add songs manually until song search is available.
        Use the arrows to set their rank.
      </p>

      {draft.map((song, index) => (
        <SongEditorRow
          key={`draft-${index}`}
          song={song}
          index={index}
          totalSongs={draft.length}
          onTitleChange={onTitleChange}
          onArtistChange={onArtistChange}
          onMoveSong={onMoveSong}
          onRemoveSong={onRemoveSong}
        />
      ))}

      {renderAddSongButton()}

      <div className="editor-footer">
        <button
          className="button button-dark"
          disabled={saving}
        >
          {saveButtonLabel}
        </button>

        {renderMessage()}
      </div>
    </form>
  )
}
