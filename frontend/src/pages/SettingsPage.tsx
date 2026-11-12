import {
  useEffect,
  useState,
} from 'react'

import SectionHeading from '../components/SectionHeading.tsx'
import {
  api,
  getErrorMessage,
  type ProfileData,
  type User,
} from '../lib/api.ts'

type SettingsPageProps = {
  user: User
  onDisplayNameChange: (displayName: string) => void
}

function getInitialDisplayName(user: User) {
  return user.display_name
}

export default function SettingsPage({
  user,
  onDisplayNameChange,
}: SettingsPageProps) {
  const initialDisplayName = getInitialDisplayName(user)

  const [displayName, setDisplayName] = useState(initialDisplayName)
  const [bio, setBio] = useState('')
  const [isTop10Public, setIsTop10Public] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadProfile() {
      try {
        const profile = await api<ProfileData>(
          '/api/v1/profiles/me',
        )

        if (cancelled) {
          return
        }

        let loadedBio = ''

        if (typeof profile.bio === 'string') {
          loadedBio = profile.bio
        }

        let top10IsPublic = false

        if (typeof profile.is_top10_public === 'boolean') {
          top10IsPublic = profile.is_top10_public
        }

        setDisplayName(profile.display_name)
        setBio(loadedBio)
        setIsTop10Public(top10IsPublic)
      } catch (error) {
        if (cancelled) {
          return
        }

        const message = getErrorMessage(
          error,
          'Could not load profile details.',
        )

        setSaveMessage(message)
      }
    }

    void loadProfile()

    return () => {
      cancelled = true
    }
  }, [])

  async function saveProfile() {
    const nextDisplayName = displayName.trim()

    if (!nextDisplayName) {
      setSaveMessage('Display name cannot be empty.')
      return
    }

    setSaving(true)
    setSaveMessage('')

    try {
      const profile = await api<ProfileData>(
        '/api/v1/profiles/me',
        {
          method: 'POST',
          body: JSON.stringify({
            display_name: nextDisplayName,
            bio,
            is_top10_public: isTop10Public,
          }),
        },
      )

      let savedDisplayName = nextDisplayName

      if (typeof profile.display_name === 'string') {
        savedDisplayName = profile.display_name
      }

      setDisplayName(savedDisplayName)
      onDisplayNameChange(savedDisplayName)
      setSaveMessage('Profile name saved.')
    } catch (error) {
      const message = getErrorMessage(
        error,
        'Could not save profile name.',
      )

      setSaveMessage(message)
    } finally {
      setSaving(false)
    }
  }

  function renderSaveMessage() {
    if (!saveMessage) {
      return null
    }

    return (
      <p
        id="settings-save-message"
        className="settings-save-message"
        role="status"
      >
        {saveMessage}
      </p>
    )
  }

  let saveButtonLabel = 'Save changes'

  if (saving) {
    saveButtonLabel = 'Saving…'
  }

  let saveMessageId: string | undefined

  if (saveMessage) {
    saveMessageId = 'settings-save-message'
  }

  return (
    <div className="settings-grid">
      <section className="card settings-card">
        <SectionHeading
          eyebrow="THE BASICS"
          title="Profile details"
        />

        <label className="field-label">
          Display name

          <input
            value={displayName}
            maxLength={100}
            required
            aria-describedby={saveMessageId}
            onChange={(event) => {
              setDisplayName(event.target.value)
            }}
          />
        </label>

        <label className="field-label">
          About you

          <textarea
            value={bio}
            rows={3}
            maxLength={5000}
            onChange={(event) => {
              setBio(event.target.value)
            }}
          />
        </label>

        <button
          className="button button-dark"
          type="button"
          disabled={saving}
          onClick={() => {
            void saveProfile()
          }}
        >
          {saveButtonLabel}
        </button>

        {renderSaveMessage()}
      </section>

      <section className="card settings-card">
        <SectionHeading
          eyebrow="YOUR PRIVACY"
          title="Visibility"
        />

        <label className="setting-toggle">
          <span>
            <strong>Public Top 10</strong>

            <small>
              Let anyone see the songs on your list.
            </small>
          </span>

          <input
            type="checkbox"
            checked={isTop10Public}
            onChange={(event) => {
              setIsTop10Public(event.target.checked)
            }}
          />
        </label>
      </section>
    </div>
  )
}
