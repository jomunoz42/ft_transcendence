import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import MemberTop10 from '../components/ProfileTop10.tsx'
import ProfileComments from '../components/ProfileComments.tsx'
import {
  api,
  getErrorMessage,
  type ProfileData,
  type User,
} from '../lib/api.ts'
import { initialsFor } from '../lib/format.ts'

type MemberProfilePageProps = {
  user: User
  userId: number
}

export default function MemberProfilePage({
  user,
  userId,
}: MemberProfilePageProps) {
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchProfile = useCallback(async () => {
    const profileData = await api<ProfileData>(
      `/api/v1/profiles/${userId}`,
    )

    return profileData
  }, [userId])

  const loadProfile = useCallback(async () => {
    const loadedProfile = await fetchProfile()
    setProfile(loadedProfile)
  }, [fetchProfile])

  useEffect(() => {
    let cancelled = false

    async function loadInitialProfile() {
      try {
        const loadedProfile = await fetchProfile()

        if (cancelled) {
          return
        }

        setProfile(loadedProfile)
      } catch (reason) {
        if (cancelled) {
          return
        }

        setError(getErrorMessage(reason, 'Could not load this profile.'))
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadInitialProfile()

    return () => {
      cancelled = true
    }
  }, [fetchProfile])

  if (loading) {
    return (
      <p className="social-state">
        Loading profile…
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

  if (!profile) {
    return (
      <p
        className="social-state"
        role="alert"
      >
        Profile not found.
      </p>
    )
  }

  let bio = 'No bio added yet.'

  if (profile.bio) {
    bio = profile.bio
  }

  const initials = initialsFor(profile.display_name)
  const isFriend = Array.isArray(profile.comments)

  return (
    <>
      <section className="card profile-hero">
        <div className="avatar avatar-profile">
          {initials}
        </div>

        <div className="profile-hero-copy">
          <span className="eyebrow">
            LISTENER PROFILE
          </span>

          <h2>{profile.display_name}</h2>
          <p>{bio}</p>
        </div>
      </section>

      <div className="profile-body">
        <MemberTop10
          displayName={profile.display_name}
          entries={profile.top10_entries}
        />

        <ProfileComments
          user={user}
          userId={userId}
          comments={profile.comments}
          isFriend={isFriend}
          onReload={loadProfile}
        />
      </div>
    </>
  )
}
