import { ExternalLink } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import { sourceUrl, splitPath } from '../lib/format'
import { useRepoLinks } from '../lib/repoLinks'

function delay(step: number): CSSProperties {
  return { ['--d' as string]: step }
}

export function Panel({
  index,
  title,
  step = 0,
  id,
  action,
  children,
}: {
  index: string
  title: string
  step?: number
  id?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={id ? `${id}-title` : undefined}
      className="panel reveal min-w-0 scroll-mt-24 p-5 sm:p-6"
      style={delay(step)}
    >
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 id={id ? `${id}-title` : undefined} className="kicker flex items-center gap-2.5">
          <span className="text-signal">{index}</span>
          <span className="h-px w-5 bg-line" aria-hidden="true" />
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

export function BarList({
  items,
  hatched = false,
  empty = 'Nothing in this group.',
}: {
  items: [string, number][]
  hatched?: boolean
  empty?: string
}) {
  if (items.length === 0) {
    return <p className="text-sm text-ink-soft">{empty}</p>
  }
  const sorted = [...items].sort((a, b) => b[1] - a[1])
  const max = Math.max(...sorted.map(([, count]) => count))
  return (
    <ul className="space-y-3.5">
      {sorted.map(([label, count], index) => (
        <li key={label}>
          <div className="mb-1.5 flex items-baseline justify-between gap-4 text-sm">
            <span className="truncate text-ink">{label}</span>
            <span className="font-mono text-xs tabular-nums text-ink-soft">{count}</span>
          </div>
          <div className="bar-track">
            <div
              className={`bar-fill ${hatched ? 'bar-fill--hatched' : ''}`}
              style={{ width: `${(count / max) * 100}%`, ...delay(index) }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function Stat({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 border-l-[1.5px] border-line pl-4">
      <dt className="kicker">{label}</dt>
      <dd
        className={`mt-2 truncate text-ink ${
          mono ? 'font-mono text-lg' : 'font-display text-4xl leading-none sm:text-5xl'
        }`}
      >
        {value}
      </dd>
    </div>
  )
}

/** A repository path that links to the exact file and line on GitHub. */
export function SourceLink({
  path,
  line,
  className = '',
}: {
  path: string
  line?: number | null
  className?: string
}) {
  const links = useRepoLinks()
  const [folder, file] = splitPath(path)
  const label = (
    <>
      <span className="text-ink-faint">{folder}</span>
      <span className="text-ink">{file}</span>
      {line ? <span className="text-ink-faint">:{line}</span> : null}
    </>
  )
  if (!links) return <span className={`break-all font-mono text-xs ${className}`}>{label}</span>
  return (
    <a
      href={sourceUrl(links.htmlUrl, links.branch, path, line)}
      target="_blank"
      rel="noreferrer noopener"
      className={`group inline-flex max-w-full items-baseline gap-1 break-all font-mono text-xs hover:underline ${className}`}
      title={`Open ${path}${line ? ` at line ${line}` : ''} on GitHub`}
    >
      <span className="min-w-0">{label}</span>
      <ExternalLink
        size={11}
        className="shrink-0 self-center text-ink-faint group-hover:text-signal"
        aria-hidden="true"
      />
    </a>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="border-[1.5px] border-dashed border-line px-4 py-6 text-center text-sm text-ink-soft">
      {children}
    </p>
  )
}

export function Notice({
  tone = 'warn',
  children,
}: {
  tone?: 'warn' | 'danger'
  children: ReactNode
}) {
  const styles =
    tone === 'warn'
      ? 'border-warn-border bg-warn-bg text-warn-text'
      : 'border-danger-border bg-danger-bg text-danger-text'
  return <div className={`border-[1.5px] p-3 text-sm ${styles}`}>{children}</div>
}

export function Toggle({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: string; label: string }[]
  value: string
  onChange: (value: string) => void
  label: string
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex border-[1.5px] border-ink">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={`px-3 py-1.5 font-mono text-[0.7rem] uppercase tracking-[0.12em] transition-colors ${
            value === option.value ? 'bg-ink text-paper' : 'text-ink-soft hover:text-ink'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function Checkbox({
  checked,
  onChange,
  children,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  children: ReactNode
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink-soft">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 accent-[var(--signal)]"
      />
      {children}
    </label>
  )
}
