import friendsIcon from '../assets/icons/friendsIcon.svg'
import homeIcon from '../assets/icons/homeIcon.svg'
import settingsIcon from '../assets/icons/settingsIcon.svg'

export type Route =
  | '/'
  | '/friends'
  | '/settings'
  | '/login'
  | '/register'
  | `/members/${number}`

type NavigationLink = {
  to: Route
  label: string
  icon: string
}

function normalizePath(path: string) {
  if (path.length > 1 && path.endsWith('/')) {
    return path.slice(0, -1)
  }

  return path
}

function isMemberPath(path: string) {
  const memberPathPattern = /^\/members\/\d+$/

  return memberPathPattern.test(path)
}

export function currentPath(): Route {
  const path = normalizePath(window.location.pathname)

  if (isMemberPath(path)) {
    return path as Route
  }

  if (path === '/') {
    return '/'
  }

  if (path === '/friends') {
    return '/friends'
  }

  if (path === '/settings') {
    return '/settings'
  }

  if (path === '/login') {
    return '/login'
  }

  if (path === '/register') {
    return '/register'
  }

  return '/'
}

export const links: NavigationLink[] = [
  {
    to: '/',
    label: 'Home',
    icon: homeIcon,
  },
  {
    to: '/friends',
    label: 'Friends',
    icon: friendsIcon,
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: settingsIcon,
  },
]