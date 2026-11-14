import { Link } from 'react-router'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

export function NotFound() {
  useDocumentTitle('Page not found | RepoLens')
  return (
    <div>
      <h1 className="font-display text-5xl leading-none">Page not found</h1>
      <p className="mt-2 text-ink-soft">That address does not exist.</p>
      <Link to="/" className="mt-4 inline-block text-signal-deep underline">
        Back to RepoLens
      </Link>
    </div>
  )
}
