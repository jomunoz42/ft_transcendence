import {
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  links,
  type Route,
} from '../app/routes.tsx'
import logoIcon from '../assets/icons/logoIcon.png'
import type { User } from '../lib/api.ts'
import { initialsFor } from '../lib/format.ts'
import Link from './Link.tsx'

type SidebarProps = {
  path: Route
  user: User
  onLogout: () => Promise<void>
}

type NavigationItem = (typeof links)[number]

type NavigationLinkProps = {
  item: NavigationItem
  path: Route
}

type AccountActionProps = {
  loggingOut: boolean
  onLogout: () => void
}

type ProfileMenuProps = {
  open: boolean
  displayName: string
  loggingOut: boolean
  logoutError: string
  onLogout: () => void
}

function NavigationLink({
  item,
  path,
}: NavigationLinkProps) {
  let className = 'nav-link'
  let currentPage: 'page' | undefined

  if (path === item.to) {
    className = 'nav-link active'
    currentPage = 'page'
  }

  return (
    <Link
      to={item.to}
      className={className}
      aria-current={currentPage}
    >
      <span
        className="nav-icon"
        aria-hidden="true"
      >
        <img
          src={item.icon}
          alt=""
        />
      </span>

      <span>{item.label}</span>
    </Link>
  )
}

function AccountAction({
  loggingOut,
  onLogout,
}: AccountActionProps) {
  let buttonLabel = 'Log out'

  if (loggingOut) {
    buttonLabel = 'Signing out…'
  }

  return (
    <button
      type="button"
      role="menuitem"
      className="profile-menu-action"
      onClick={onLogout}
      disabled={loggingOut}
    >
      {buttonLabel}
    </button>
  )
}

function LogoutError({
  message,
}: {
  message: string
}) {
  if (!message) {
    return null
  }

  return (
    <p
      className="profile-menu-error"
      role="alert"
    >
      {message}
    </p>
  )
}

function ProfileMenu({
  open,
  displayName,
  loggingOut,
  logoutError,
  onLogout,
}: ProfileMenuProps) {
  if (!open) {
    return null
  }

  return (
    <div
      className="profile-menu"
      id="profile-menu"
      role="menu"
      aria-label="Account menu"
    >
      <p className="profile-menu-name">
        {displayName}
      </p>

      <AccountAction
        loggingOut={loggingOut}
        onLogout={onLogout}
      />

      <LogoutError message={logoutError} />
    </div>
  )
}

export default function Sidebar({
  path,
  user,
  onLogout,
}: SidebarProps) {
  const displayName = user.display_name
  const initials = initialsFor(displayName)

  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState('')

  const profileMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!profileMenuOpen) {
      return
    }

    function dismissMenu(event: MouseEvent | KeyboardEvent) {
      if (event instanceof KeyboardEvent) {
        if (event.key === 'Escape') {
          setProfileMenuOpen(false)
        }

        return
      }

      if (!(event.target instanceof Node)) {
        return
      }

      const profileMenu = profileMenuRef.current

      if (profileMenu !== null) {
        if (profileMenu.contains(event.target)) {
          return
        }
      }

      setProfileMenuOpen(false)
    }

    document.addEventListener('mousedown', dismissMenu)
    document.addEventListener('keydown', dismissMenu)

    return () => {
      document.removeEventListener('mousedown', dismissMenu)
      document.removeEventListener('keydown', dismissMenu)
    }
  }, [profileMenuOpen])

  function toggleProfileMenu() {
    setProfileMenuOpen((menuOpen) => {
      if (menuOpen) {
        return false
      }

      return true
    })
  }

  async function logout() {
    setLoggingOut(true)
    setLogoutError('')

    try {
      await onLogout()
    } catch (error) {
      let errorMessage = 'Could not sign out. Please try again.'

      if (error instanceof Error) {
        errorMessage = error.message
      }

      setLogoutError(errorMessage)
      setLoggingOut(false)
    }
  }

  function handleLogoutClick() {
    void logout()
  }

  return (
    <aside className="sidebar">
      <Link
        to="/"
        className="brand"
        aria-label="MyPlaylist home"
      >
        <img
          className="brand-mark"
          src={logoIcon}
          alt=""
        />

        <span>myplaylist</span>
      </Link>

      <nav
        className="main-nav"
        aria-label="Main navigation"
      >
        {links.map((item) => (
          <NavigationLink
            key={item.to}
            item={item}
            path={path}
          />
        ))}
      </nav>

      <div
        className="sidebar-bottom"
        ref={profileMenuRef}
      >
        <button
          className="mini-profile"
          type="button"
          aria-label={`Open account menu for ${displayName}`}
          aria-haspopup="menu"
          aria-expanded={profileMenuOpen}
          aria-controls="profile-menu"
          onClick={toggleProfileMenu}
        >
          <span
            className="avatar avatar-small sidebar-profile-avatar"
            aria-hidden="true"
          >
            {initials}
          </span>

          <span>
            <strong>{displayName}</strong>
            <small>Account menu</small>
          </span>
        </button>

        <ProfileMenu
          open={profileMenuOpen}
          displayName={displayName}
          loggingOut={loggingOut}
          logoutError={logoutError}
          onLogout={handleLogoutClick}
        />
      </div>
    </aside>
  )
}
