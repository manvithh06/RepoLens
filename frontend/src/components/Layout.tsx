import { Link, NavLink, Outlet } from 'react-router'
import { ThemeToggle } from './ThemeToggle'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm transition-colors hover:text-ink ${isActive ? 'text-ink underline underline-offset-4' : 'text-ink-soft'}`

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b-[1.5px] border-ink bg-paper/90 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5">
            <img src="/favicon.svg" alt="" width={24} height={24} />
            <span className="font-display text-2xl leading-none">RepoLens</span>
          </Link>
          <nav aria-label="Site" className="flex items-center gap-5">
            <NavLink to="/privacy" className={navClass}>
              Privacy
            </NavLink>
            <NavLink to="/terms" className={navClass}>
              Terms
            </NavLink>
            <ThemeToggle />
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-14 sm:px-6 sm:py-20">
        <Outlet />
      </main>

      <footer className="border-t-[1.5px] border-ink">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:flex-row sm:items-end sm:justify-between sm:px-6">
          <div>
            <p className="font-display text-3xl leading-none">RepoLens</p>
            <p className="mt-2 text-sm text-ink-soft">
              Reads public GitHub repositories. Clones are deleted after each analysis.
            </p>
          </div>
          <div className="flex gap-5 text-sm text-ink-soft">
            <Link to="/privacy" className="hover:text-ink hover:underline">
              Privacy Policy
            </Link>
            <Link to="/terms" className="hover:text-ink hover:underline">
              Terms and Conditions
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
