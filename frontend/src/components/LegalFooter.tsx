import Link from './Link.tsx'

export default function LegalFooter() {
  return (
    <footer className="legal-footer" aria-label="Legal information">
      <Link to="/privacy">Privacy Policy</Link>
      <Link to="/terms">Terms of Service</Link>
    </footer>
  )
}
