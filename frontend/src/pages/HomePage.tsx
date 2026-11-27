import { useEffect, useState } from 'react'

import ProfileCard from '../components/ProfileCard.tsx'
import SectionHeading from '../components/SectionHeading.tsx'
import SongRows from '../components/SongRows.tsx'
import Top10SongPicker from '../components/Top10SongPicker.tsx'
import {
  api,
  getErrorMessage,
  type ProfileData,
  type Top10Entry,
  type User,
} from '../lib/api.ts'
import {
  addTop10Entry,
  type SpotifySong,
} from '../lib/top10Api.ts'
import type { PresenceStatus } from '../websocket/useWebSocket.ts'

type HomePageProps = {
  user: User
  presenceStatus: PresenceStatus
}

function firstAvailableRank(entries: Top10Entry[] = []) {
  const usedRanks = new Set(entries.map((entry) => entry.rank))

  for (let rank = 1; rank <= 10; rank += 1) {
    if (!usedRanks.has(rank)) {
      return rank
    }
  }

  return null
}

function loadProfile() {
  return api<ProfileData>('/api/v1/profiles/me')
}

export default function HomePage({
  user,
  presenceStatus,
}: HomePageProps) {
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [addingSong, setAddingSong] = useState(false)
  const [top10Message, setTop10Message] = useState('')

  useEffect(() => {
    let cancelled = false

    void loadProfile()
      .then((loadedProfile) => {
        if (!cancelled) {
          setProfile(loadedProfile)
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(getErrorMessage(reason, 'Could not load your Top 10.'))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [user])

  function openPicker() {
    setTop10Message('')
    setPickerOpen(true)
  }

  function closePicker() {
    setTop10Message('')
    setPickerOpen(false)
  }

  async function addSong(song: SpotifySong) {
    const rank = firstAvailableRank(profile?.top10_entries)

    if (rank === null) {
      setTop10Message('Your Top 10 already has ten songs.')
      return
    }

    setAddingSong(true)
    setTop10Message('')

    try {
      await addTop10Entry(user.id, song, rank)

      const refreshedProfile = await loadProfile()
      setProfile(refreshedProfile)
      setPickerOpen(false)
      setTop10Message(`${song.title} was added to your Top 10.`)
    } catch (reason) {
      setTop10Message(getErrorMessage(reason, 'Could not add this song.'))
    } finally {
      setAddingSong(false)
    }
  }

  function renderMessage() {
    if (!top10Message) {
      return null
    }

    return (
      <p className="social-state" role="status">
        {top10Message}
      </p>
    )
  }

  function renderTop10Content() {
    if (pickerOpen) {
      return (
        <>
          <Top10SongPicker
            adding={addingSong}
            onSelect={addSong}
          />
          {renderMessage()}
        </>
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
      </div>
    )
  }

  function renderTop10Actions() {
    if (pickerOpen) {
      return null
    }

    const entries = profile?.top10_entries ?? []

    return (
      <>
        {entries.length < 10 && (
          <button
            className="add-song"
            type="button"
            disabled={loading || Boolean(error)}
            onClick={openPicker}
          >
            ＋ <span>Add a song to your list</span>
          </button>
        )}

        {renderMessage()}
      </>
    )
  }

  const pickerAction = pickerOpen ? (
    <button
      className="text-button"
      type="button"
      disabled={addingSong}
      onClick={closePicker}
    >
      Cancel
    </button>
  ) : undefined

  return (
    <div className="home-grid">
      <section className="card top10-card">
        <SectionHeading
          title="Your Top 10"
          action={pickerAction}
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
