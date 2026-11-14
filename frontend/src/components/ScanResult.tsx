import { ExternalLink, TriangleAlert } from 'lucide-react'
import type { CSSProperties, ReactNode } from 'react'
import { formatBytes } from '../lib/format'
import { SKIP_LABELS } from '../lib/labels'
import type { RepositoryScan } from '../types/api'

function delay(step: number): CSSProperties {
  return { ['--d' as string]: step }
}

function Panel({
  index,
  title,
  step,
  children,
}: {
  index: string
  title: string
  step: number
  children: ReactNode
}) {
  return (
    <section className="panel reveal p-6" style={delay(step)}>
      <h2 className="kicker mb-5 flex items-center gap-2.5">
        <span className="text-signal">{index}</span>
        <span className="h-px w-5 bg-line" aria-hidden="true" />
        {title}
      </h2>
      {children}
    </section>
  )
}

function BarList({ items, hatched = false }: { items: [string, number][]; hatched?: boolean }) {
  if (items.length === 0) {
    return <p className="text-sm text-ink-soft">Nothing in this group.</p>
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

function Stat({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="border-l-[1.5px] border-line pl-4">
      <dt className="kicker">{label}</dt>
      <dd
        className={`mt-2 text-ink ${
          mono ? 'font-mono text-lg' : 'font-display text-4xl leading-none sm:text-5xl'
        }`}
      >
        {value}
      </dd>
    </div>
  )
}

function splitPath(path: string): [string, string] {
  const cut = path.lastIndexOf('/')
  return cut === -1 ? ['', path] : [path.slice(0, cut + 1), path.slice(cut + 1)]
}

export function ScanResult({ scan }: { scan: RepositoryScan }) {
  const { repository } = scan

  const skipped = Object.entries(scan.skipped).map(
    ([reason, count]): [string, number] => [SKIP_LABELS[reason] ?? reason, count],
  )
  const extensions = Object.entries(scan.extensions)

  return (
    <div className="space-y-8">
      <Panel index="01" title="Repository" step={0}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <a
              href={repository.html_url}
              target="_blank"
              rel="noreferrer noopener"
              className="group inline-flex items-center gap-2 font-display text-3xl leading-tight text-ink hover:text-signal sm:text-4xl"
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
          <Stat label="Language" value={repository.primary_language ?? 'Not reported'} mono />
          <Stat label="Branch" value={repository.default_branch} mono />
        </dl>
      </Panel>

      {scan.truncated && (
        <div
          role="status"
          className="reveal flex items-start gap-3 border-[1.5px] border-warn-border bg-warn-bg p-4 text-sm text-warn-text"
          style={delay(1)}
        >
          <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <p>
            This repository reached a size limit, so only part of it was kept. The files closest
            to the project root are kept first.
          </p>
        </div>
      )}

      <div className="grid items-start gap-8 md:grid-cols-2">
        <Panel index="02" title="File types kept" step={1}>
          <BarList items={extensions} />
        </Panel>
        <Panel index="03" title="Skipped" step={2}>
          <BarList items={skipped} hatched />
        </Panel>
      </div>

      <Panel
        index="04"
        title={`First ${scan.sample_paths.length} of ${scan.file_count} files`}
        step={3}
      >
        <ul className="max-h-80 overflow-auto pr-2 font-mono text-[0.8rem] leading-7">
          {scan.sample_paths.map((path) => {
            const [folder, file] = splitPath(path)
            return (
              <li key={path} className="truncate border-b border-dashed border-line last:border-0">
                <span className="text-ink-faint">{folder}</span>
                <span className="text-ink">{file}</span>
              </li>
            )
          })}
        </ul>
      </Panel>
    </div>
  )
}
