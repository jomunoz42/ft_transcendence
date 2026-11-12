import type { ReactNode } from 'react'

type SectionHeadingProps = {
  eyebrow?: string
  title: string
  action?: ReactNode
}

export default function SectionHeading({
  eyebrow,
  title,
  action,
}: SectionHeadingProps) {
  let headingClassName = ''
  let eyebrowContent: ReactNode = null

  if (!eyebrow) {
    headingClassName = 'section-heading-no-eyebrow'
  }

  if (eyebrow) {
    eyebrowContent = (
      <span className="eyebrow">
        {eyebrow}
      </span>
    )
  }

  return (
    <div className="section-heading">
      <div className={headingClassName}>
        {eyebrowContent}
        <h2>{title}</h2>
      </div>

      {action}
    </div>
  )
}