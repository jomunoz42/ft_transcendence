import type { ReactNode } from 'react'

import {
  links,
  type Route,
} from '../app/routes.tsx'
import moonIcon from '../assets/icons/moonIcon.svg'
import sunIcon from '../assets/icons/sunIcon.svg'
import type { User } from '../lib/api.ts'
import Sidebar from './Sidebar.tsx'

type Theme = 'light' | 'dark'

type ShellProps = {
  path: Route
  children: ReactNode
  theme: Theme
  user: User
  onToggleTheme: () => void
  onLogout: () => Promise<void>
}

function getPageTitle(path: Route) {
  const currentLink = links.find((item) => item.to === path)

  if (currentLink) {
    return currentLink.label
  }

  if (path.startsWith('/members/')) {
    return 'Listener profile'
  }

  return 'MyPlaylist'
}

export default function Shell({
  path,
  children,
  theme,
  user,
  onToggleTheme,
  onLogout,
}: ShellProps) {
  const pageTitle = getPageTitle(path)
  const darkModeEnabled = theme === 'dark'

  let themeTitle = 'Dark mode off'
  let themeIcon = moonIcon

  if (darkModeEnabled) {
    themeTitle = 'Dark mode on'
    themeIcon = sunIcon
  }

  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
      >
        Skip to content
      </a>

      <Sidebar
        path={path}
        user={user}
        onLogout={onLogout}
      />

      <div className="main-column">
        <header className="topbar">
          <div>
            <h1>{pageTitle}</h1>
          </div>

          <div className="topbar-actions">
            <button
              className="theme-switch"
              type="button"
              role="switch"
              aria-checked={darkModeEnabled}
              onClick={onToggleTheme}
              aria-label="Dark mode"
              title={themeTitle}
            >
              <span className="theme-switch-thumb">
                <img
                  src={themeIcon}
                  alt=""
                  aria-hidden="true"
                />
              </span>
            </button>
          </div>
        </header>

        <main
          id="main-content"
          className="page-content"
          tabIndex={-1}
        >
          {children}
        </main>
      </div>
    </div>
  )
}
