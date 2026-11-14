import { ExternalLink, TriangleAlert } from 'lucide-react'
import { formatBytes } from '../../lib/format'
import type { LanguageStat, RepositoryAnalysis } from '../../types/api'
import { EmptyState, Notice, Panel, Stat } from '../ui'

const MAX_SEGMENTS = 7

function segments(code: LanguageStat[]): { name: string; percent: number; files: number }[] {
  const top = code.slice(0, MAX_SEGMENTS)
  const rest = code.slice(MAX_SEGMENTS)
  const list = top.map(({ name, percent, files }) => ({ name, percent, files }))
  if (rest.length > 0) {
    list.push({
      name: `${rest.length} more`,
      percent: Math.round(rest.reduce((sum, item) => sum + item.percent, 0) * 10) / 10,
      files: rest.reduce((sum, item) => sum + item.files, 0),
    })
  }
  return list
}

export function LanguageBar({ code }: { code: LanguageStat[] }) {
  if (code.length === 0) {
    return <EmptyState>No programming language files were found.</EmptyState>
  }
  const items = segments(code)
  return (
    <div>
      <div
        className="lang-bar"
        role="img"
        aria-label={items.map((item) => `${item.name} ${item.percent}%`).join(', ')}
      >
        {items.map((item, index) => (
          <span
            key={item.name}
            style={{ width: `${item.percent}%`, background: `var(--cat-${index + 1})` }}
          />
        ))}
      </div>
      <ul className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item, index) => (
          <li key={item.name} className="flex min-w-0 items-baseline gap-2">
            <span
              className="inline-block size-2.5 shrink-0 translate-y-px border border-ink"
              style={{ background: `var(--cat-${index + 1})` }}
              aria-hidden="true"
            />
            <span className="truncate text-ink">{item.name}</span>
            <span className="ml-auto font-mono text-xs tabular-nums text-ink-soft">
              {item.percent}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Overview({ analysis, index }: { analysis: RepositoryAnalysis; index: string }) {
  const { scan, languages } = analysis
  const { repository } = scan
  return (
    <Panel index={index} title="Overview" id="overview">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <a
            href={repository.html_url}
            target="_blank"
            rel="noreferrer noopener"
            className="group inline-flex max-w-full items-center gap-2 font-display text-3xl leading-tight text-ink hover:text-signal sm:text-4xl"
          >
            <span className="truncate">{repository.full_name}</span>
            <ExternalLink
              size={18}
              className="shrink-0 text-ink-faint group-hover:text-signal"
              aria-hidden="true"
            />
          </a>
          {repository.description && (
            <p className="mt-2 max-w-2xl text-ink-soft">{repository.description}</p>
          )}
        </div>
        <span className="kicker border border-line px-2 py-1">Public</span>
      </div>

      <dl className="mt-8 grid grid-cols-2 gap-x-6 gap-y-8 lg:grid-cols-4">
        <Stat label="Files kept" value={String(scan.file_count)} />
        <Stat label="Source size" value={formatBytes(scan.total_bytes)} />
        <Stat label="Main language" value={languages.primary ?? 'None found'} mono />
        <Stat label="Branch" value={repository.default_branch} mono />
      </dl>

      <div className="mt-8">
        <p className="kicker mb-3">Code by size</p>
        <LanguageBar code={languages.code} />
      </div>

      {scan.truncated && (
        <div className="mt-6">
          <Notice>
            <span className="flex items-start gap-2">
              <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              This repository reached a size limit, so only part of it was analysed. Files
              closest to the project root are kept first.
            </span>
          </Notice>
        </div>
      )}
    </Panel>
  )
}
