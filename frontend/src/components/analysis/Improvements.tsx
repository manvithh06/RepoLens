import { useState } from 'react'
import { formatCount } from '../../lib/format'
import type { Finding, Severity } from '../../types/api'
import { EmptyState, Panel, SourceLink, Toggle } from '../ui'

const SEVERITY_STYLE: Record<Severity, string> = {
  high: 'border-danger-border bg-danger-bg text-danger-text',
  medium: 'border-warn-border bg-warn-bg text-warn-text',
  low: 'border-line bg-paper text-ink-soft',
}

const EVIDENCE_PREVIEW = 3

function FindingCard({ finding }: { finding: Finding }) {
  const [showAll, setShowAll] = useState(false)
  const evidence = showAll ? finding.evidence : finding.evidence.slice(0, EVIDENCE_PREVIEW)
  return (
    <li className="border-[1.5px] border-ink bg-surface p-4 sm:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`kicker border-[1.5px] px-1.5 py-0.5 ${SEVERITY_STYLE[finding.severity]}`}>
          {finding.severity}
        </span>
        <span
          className={`kicker border px-1.5 py-0.5 ${
            finding.status === 'Confirmed' ? 'border-signal text-signal-deep' : 'border-dashed border-ink-faint'
          }`}
          title={
            finding.status === 'Confirmed'
              ? 'Found by a deterministic check of the files'
              : 'A heuristic match. Check it before acting on it.'
          }
        >
          {finding.status}
        </span>
        <span className="kicker text-ink-faint">{finding.category}</span>
      </div>
      <h3 className="mt-3 text-base font-medium text-ink">{finding.title}</h3>
      {finding.detail && <p className="mt-1 break-words text-sm text-ink-soft">{finding.detail}</p>}

      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="kicker mb-1">Why it matters</dt>
          <dd className="leading-6 text-ink">{finding.why}</dd>
        </div>
        <div>
          <dt className="kicker mb-1">Fix</dt>
          <dd className="leading-6 text-ink">{finding.fix}</dd>
        </div>
      </dl>

      {finding.evidence.length > 0 && (
        <div className="mt-4 border-t border-dashed border-line pt-3">
          <p className="kicker mb-2">
            Evidence
            {finding.evidence_total > finding.evidence.length &&
              ` (first ${finding.evidence.length} of ${finding.evidence_total})`}
          </p>
          <ul className="space-y-1">
            {evidence.map((item) => (
              <li key={`${item.path}:${item.line ?? ''}`}>
                <SourceLink path={item.path} line={item.line} />
              </li>
            ))}
          </ul>
          {finding.evidence.length > EVIDENCE_PREVIEW && (
            <button
              type="button"
              onClick={() => setShowAll(!showAll)}
              className="mt-2 text-xs text-ink-soft underline hover:text-ink"
            >
              {showAll ? 'Show fewer' : `Show all ${finding.evidence.length}`}
            </button>
          )}
        </div>
      )}
    </li>
  )
}

export function Improvements({ findings, index }: { findings: Finding[]; index: string }) {
  const [severity, setSeverity] = useState<'all' | Severity>('all')
  const [category, setCategory] = useState('all')
  const categories = [...new Set(findings.map((finding) => finding.category))].sort()
  const counts = (level: Severity) => findings.filter((f) => f.severity === level).length
  const visible = findings.filter(
    (finding) =>
      (severity === 'all' || finding.severity === severity) &&
      (category === 'all' || finding.category === category),
  )

  return (
    <Panel index={index} title="Improvements" id="improvements">
      {findings.length === 0 ? (
        <EmptyState>
          None of the checks found a problem. That covers documentation, licensing, tests, CI,
          committed secrets, dependency pinning, file and function size, import cycles and linting.
        </EmptyState>
      ) : (
        <>
          <dl className="mb-6 grid grid-cols-3 gap-4">
            {(['high', 'medium', 'low'] as const).map((level) => (
              <div key={level} className="border-l-[1.5px] border-line pl-4">
                <dt className="kicker">{level}</dt>
                <dd className="mt-1 font-display text-4xl leading-none text-ink">{counts(level)}</dd>
              </div>
            ))}
          </dl>

          <div className="mb-5 flex flex-wrap items-center gap-3">
            <Toggle
              label="Filter by severity"
              value={severity}
              onChange={(value) => setSeverity(value as 'all' | Severity)}
              options={[
                { value: 'all', label: 'All' },
                { value: 'high', label: 'High' },
                { value: 'medium', label: 'Med' },
                { value: 'low', label: 'Low' },
              ]}
            />
            <label className="flex min-w-0 items-center gap-2 text-sm text-ink-soft">
              <span className="shrink-0">Category</span>
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="min-w-0 rounded-sm border-[1.5px] border-ink bg-surface px-2 py-1 text-sm text-ink"
              >
                <option value="all">All categories</option>
                {categories.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {visible.length === 0 ? (
            <EmptyState>No findings match these filters.</EmptyState>
          ) : (
            <ol className="space-y-4">
              {visible.map((finding) => (
                <FindingCard key={finding.id} finding={finding} />
              ))}
            </ol>
          )}
          <p className="mt-5 text-xs text-ink-faint">
            Confirmed means a deterministic check found it in the files. Potential means a pattern
            match that needs a human look. Ranked by severity, then impact.{' '}
            {formatCount(findings.length, 'finding')} in total.
          </p>
        </>
      )}
    </Panel>
  )
}
