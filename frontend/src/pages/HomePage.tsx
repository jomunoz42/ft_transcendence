import {
  useEffect,
  useState,
  type FormEvent,
} from 'react'

import ProfileCard from '../components/ProfileCard.tsx'
import SectionHeading from '../components/SectionHeading.tsx'
import SongRows from '../components/SongRows.tsx'
import Top10Editor, {
  type SongDraft,
} from '../components/Top10.tsx'
import {
  api,
  getErrorMessage,
  type ProfileData,
  type User,
} from '../lib/api.ts'
import { compareTop10ByRank } from '../lib/format.ts'
import type { PresenceStatus } from '../websocket/useWebSocket.ts'

type HomePageProps = {
  user: User
  presenceStatus: PresenceStatus
}

function createDraft(profile: ProfileData | null) {
  const entries = profile?.top10_entries

  if (!entries) {
    return []
  }

  const orderedEntries = [...entries]

  orderedEntries.sort(compareTop10ByRank)

  return orderedEntries.map((entry) => {
    let title = ''
    let artist = ''

    if (entry.song?.title) {
      title = entry.song.title
    }

    if (entry.song?.artist) {
      artist = entry.song.artist
    }

    return {
      title,
      artist,
    }
  })
}

function validateDraft(draft: SongDraft[]) {
  for (const song of draft) {
    if (!song.title.trim()) {
      return 'Every song needs a title and artist.'
    }

    if (!song.artist.trim()) {
      return 'Every song needs a title and artist.'
    }
  }

  const songKeys = new Set<string>()

  for (const song of draft) {
    const title = song.title
      .trim()
      .toLocaleLowerCase()

    const artist = song.artist
      .trim()
      .toLocaleLowerCase()

    const songKey = `${title}\u0000${artist}`

    if (songKeys.has(songKey)) {
      return 'The same song cannot appear more than once.'
    }

    songKeys.add(songKey)
  }

  return ''
}

export default function HomePage({
  user,
  presenceStatus,
}: HomePageProps) {
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingTop10, setEditingTop10] = useState(false)
  const [draft, setDraft] = useState<SongDraft[]>([])
  const [savingTop10, setSavingTop10] = useState(false)
  const [top10Message, setTop10Message] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadProfile() {
      try {
        const loadedProfile = await api<ProfileData>(
          '/api/v1/profiles/me',
        )

        if (cancelled) {
          return
        }

        setProfile(loadedProfile)
      } catch (reason) {
        if (cancelled) {
          return
        }

        const message = getErrorMessage(
          reason,
          'Could not load your Top 10.',
        )

        setError(message)
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadProfile()

    return () => {
      cancelled = true
    }
  }, [user])

  function openTop10Editor() {
    const songDraft = createDraft(profile)

    setDraft(songDraft)
    setTop10Message('')
    setEditingTop10(true)
  }

  function toggleTop10Editor() {
    if (editingTop10) {
      setEditingTop10(false)
      return
    }

    openTop10Editor()
  }

  function changeSongTitle(
    index: number,
    title: string,
  ) {
    setDraft((currentDraft) => {
      return currentDraft.map((song, songIndex) => {
        if (songIndex !== index) {
          return song
        }

        return {
          ...song,
          title,
        }
      })
    })
  }

  function changeSongArtist(
    index: number,
    artist: string,
  ) {
    setDraft((currentDraft) => {
      return currentDraft.map((song, songIndex) => {
        if (songIndex !== index) {
          return song
        }

        return {
          ...song,
          artist,
        }
      })
    })
  }

  function addSong() {
    setDraft((currentDraft) => {
      return [
        ...currentDraft,
        {
          title: '',
          artist: '',
        },
      ]
    })
  }

  function removeSong(index: number) {
    setDraft((currentDraft) => {
      return currentDraft.filter((_, songIndex) => {
        return songIndex !== index
      })
    })
  }

  function moveSong(
    index: number,
    direction: -1 | 1,
  ) {
    const targetIndex = index + direction

    if (targetIndex < 0) {
      return
    }

    if (targetIndex >= draft.length) {
      return
    }

    setDraft((currentDraft) => {
      const reorderedDraft = [...currentDraft]
      const currentSong = reorderedDraft[index]

      reorderedDraft[index] = reorderedDraft[targetIndex]
      reorderedDraft[targetIndex] = currentSong

      return reorderedDraft
    })
  }

  async function saveTop10(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    const validationMessage = validateDraft(draft)

    if (validationMessage) {
      setTop10Message(validationMessage)
      return
    }

    setSavingTop10(true)
    setTop10Message('')

    try {
      const top10 = draft.map((song, index) => {
        return {
          provider: 'manual',
          provider_id: `manual-${globalThis.crypto.randomUUID()}`,
          title: song.title.trim(),
          artist: song.artist.trim(),
          rank: index + 1,
        }
      })

      await api('/api/v1/profiles/me', {
        method: 'POST',
        body: JSON.stringify({
          top10,
        }),
      })

      const refreshedProfile = await api<ProfileData>(
        '/api/v1/profiles/me',
      )

      setProfile(refreshedProfile)
      setEditingTop10(false)
      setTop10Message('Top 10 saved.')
    } catch (reason) {
      const message = getErrorMessage(
        reason,
        'Could not save your Top 10.',
      )

      setTop10Message(message)
    } finally {
      setSavingTop10(false)
    }
  }

  function renderTop10Content() {
    if (editingTop10) {
      return (
        <Top10Editor
          draft={draft}
          saving={savingTop10}
          message={top10Message}
          onSubmit={saveTop10}
          onTitleChange={changeSongTitle}
          onArtistChange={changeSongArtist}
          onMoveSong={moveSong}
          onRemoveSong={removeSong}
          onAddSong={addSong}
        />
      )
    }

    if (loading) {
      return (
        <p className="social-state">
          Loading your Top 10…
        </p>
      )
    }

    if (error) {
      return (
        <p
          className="social-state"
          role="alert"
        >
          {error}
        </p>
      )
    }

    const entries = profile?.top10_entries

    if (entries && entries.length > 0) {
      return <SongRows entries={entries} />
    }

    return (
      <div className="empty-top10">
        <p className="social-state">
          Your Top 10 is empty. Add the songs you love.
        </p>

        <button
          className="button button-outline"
          type="button"
          onClick={openTop10Editor}
        >
          Add your first song
        </button>
      </div>
    )
  }

  function renderTop10Actions() {
    if (editingTop10) {
      return null
    }

    return (
      <>
        <button
          className="add-song"
          type="button"
          onClick={openTop10Editor}
        >
          ＋ <span>Add a song to your list</span>
        </button>

        {renderTop10Message()}
      </>
    )
  }

  function renderTop10Message() {
    if (!top10Message) {
      return null
    }

    return (
      <p
        className="social-state"
        role="status"
      >
        {top10Message}
      </p>
    )
  }

  let editorButtonLabel = 'Edit list'

  if (editingTop10) {
    editorButtonLabel = 'Cancel'
  }

  const editorButton = (
    <button
      className="text-button"
      type="button"
      onClick={toggleTop10Editor}
    >
      {editorButtonLabel} <span>↗</span>
    </button>
  )

  return (
    <div className="home-grid">
      <section className="card top10-card">
        <SectionHeading
          title="Your Top 10"
          action={editorButton}
        />

        {renderTop10Content()}
        {renderTop10Actions()}
      </section>

      <aside className="right-rail">
        <ProfileCard
          user={user}
          profile={profile}
          presenceStatus={presenceStatus}
        />
      </aside>
    </div>
  )
}
