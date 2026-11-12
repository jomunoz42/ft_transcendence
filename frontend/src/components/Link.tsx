import type {
  AnchorHTMLAttributes,
  MouseEvent,
  ReactNode,
} from 'react'

import type { Route } from '../app/routes.tsx'

type LinkProps = Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  'href'
> & {
  to: Route
  children: ReactNode
}

export default function Link({
  to,
  children,
  className = '',
  onClick,
  ...props
}: LinkProps) {
  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (onClick) {
      onClick(event)
    }

    if (event.defaultPrevented) {
      return
    }

    if (event.button !== 0) {
      return
    }

    if (event.metaKey) {
      return
    }

    if (event.ctrlKey) {
      return
    }

    if (event.shiftKey) {
      return
    }

    if (event.altKey) {
      return
    }

    event.preventDefault()

    window.history.pushState({}, '', to)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }

  return (
    <a
      {...props}
      href={to}
      className={className}
      onClick={handleClick}
    >
      {children}
    </a>
  )
}