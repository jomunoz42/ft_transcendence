import {
  useEffect,
  useRef,
  useState,
} from 'react'

import Shell from '../components/Shell.tsx'
import {
  ApiError,
  api,
  type User,
} from '../lib/api.ts'
import AuthPage from '../pages/AuthPage.tsx'
import FriendsPage from '../pages/FriendsPage.tsx'
import HomePage from '../pages/HomePage.tsx'
import MemberProfilePage from '../pages/ProfilePage.tsx'
import SettingsPage from '../pages/SettingsPage.tsx'
import { useWebSocket } from '../websocket/useWebSocket.ts'
import {
  currentPath,
  type Route,
} from './routes.tsx'

type Theme = 'light' | 'dark'

function getInitialTheme(): Theme {
  const savedTheme = window.localStorage.getItem('myplaylist-theme')

  if (savedTheme === 'dark') {
    return 'dark'
  }

  return 'light'
}

export default function App() {
  const [path, setPath] = useState<Route>(currentPath)
  const [user, setUser] = useState<User | null>(null)
  const [checkingSession, setCheckingSession] = useState(true)
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  const [headerNotice, setHeaderNotice] = useState('')
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const presence = useWebSocket(user !== null)

  function handleAuthenticated(authenticatedUser: User) {
    setUser(authenticatedUser)
    window.history.replaceState({}, '', '/')
    setPath('/')
  }

  function handleDisplayNameChange(displayName: string) {
    setUser((currentUser) => {
      if (currentUser === null) {
        return null
      }

      return {
        ...currentUser,
        display_name: displayName,
      }
    })
  }

  function handleToggleTheme() {
    setTheme((currentTheme) => {
      if (currentTheme === 'light') {
        return 'dark'
      }

      return 'light'
    })
  }

  function showHeaderWarning(message: string) {
    setHeaderNotice(message)

    if (noticeTimerRef.current !== null) {
      clearTimeout(noticeTimerRef.current)
    }

    noticeTimerRef.current = setTimeout(() => {
      setHeaderNotice('')
      noticeTimerRef.current = null
    }, 5000)
  }

  useEffect(() => {
    return () => {
      if (noticeTimerRef.current !== null) {
        clearTimeout(noticeTimerRef.current)
      }
    }
  }, [])

  async function handleLogout() {
    await api<void>('/api/v1/auth/logout', {
      method: 'POST',
    })

    setUser(null)
    window.history.replaceState({}, '', '/login')
    setPath('/login')
  }

  useEffect(() => {
    function handlePopState() {
      setPath(currentPath())
    }

    window.addEventListener('popstate', handlePopState)

    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem('myplaylist-theme', theme)
  }, [theme])

  useEffect(() => {
    if (checkingSession) {
      return
    }

    if (user !== null) {
      return
    }

    if (path === '/login') {
      return
    }

    if (path === '/register') {
      return
    }

    window.history.replaceState({}, '', '/login')
  }, [checkingSession, path, user])

  useEffect(() => {
    let cancelled = false

    api<User>('/api/v1/auth/me')
      .then((currentUser) => {
        if (cancelled) {
          return
        }

        setUser(currentUser)

        const route = currentPath()
        const isAuthPage = route === '/login' || route === '/register'

        if (isAuthPage) {
          window.history.replaceState({}, '', '/')
          setPath('/')
        }
      })
      .catch((error) => {
        if (cancelled) {
          return
        }

        if (error instanceof ApiError && error.status === 401) {
          return
        }

        console.error('Could not restore session', error)
      })
      .finally(() => {
        if (cancelled) {
          return
        }

        setCheckingSession(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (checkingSession) {
    return (
      <main className="page-content">
        Loading session…
      </main>
    )
  }

  if (user === null || path === '/login' || path === '/register') {
    return (
      <AuthPage
        register={path === '/register'}
        onAuthenticated={handleAuthenticated}
      />
    )
  }

  let page = (
    <HomePage
      user={user}
      presenceStatus={presence.status}
    />
  )

  if (path === '/friends') {
    page = (
      <FriendsPage
        user={user}
        presence={presence}
        onWarning={showHeaderWarning}
      />
    )
  } else if (path === '/settings') {
    page = (
      <SettingsPage
        user={user}
        onDisplayNameChange={handleDisplayNameChange}
      />
    )
  } else if (path.startsWith('/members/')) {
    const pathParts = path.split('/')
    const memberIdText = pathParts.at(-1)
    const memberId = Number(memberIdText)

    page = (
      <MemberProfilePage
        user={user}
        userId={memberId}
      />
    )
  }

  return (
    <Shell
      path={path}
      theme={theme}
      user={user}
      headerNotice={headerNotice}
      onToggleTheme={handleToggleTheme}
      onLogout={handleLogout}
    >
      {page}
    </Shell>
  )
}
