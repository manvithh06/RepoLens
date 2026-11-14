import type { EntryPoint } from '../../types/api'
import { EmptyState, Panel, SourceLink } from '../ui'

export function EntryPoints({ entries, index }: { entries: EntryPoint[]; index: string }) {
  return (
    <Panel index={index} title="Where it starts" id="entry-points">
      {entries.length === 0 ? (
        <EmptyState>
          No entry points were found. This may be a library, or it may start in a way RepoLens
          does not recognise yet.
        </EmptyState>
      ) : (
        <ol className="divide-y divide-dashed divide-line">
          {entries.map((entry, position) => (
            <li
              key={`${entry.path}-${entry.kind}`}
              className="grid gap-x-4 gap-y-1 py-3 first:pt-0 last:pb-0 sm:grid-cols-[2rem_10rem_1fr]"
            >
              <span className="hidden font-mono text-xs text-ink-faint sm:block">
                {String(position + 1).padStart(2, '0')}
              </span>
              <span className="kicker self-center text-signal-deep">{entry.kind}</span>
              <div className="min-w-0">
                <SourceLink path={entry.path} line={entry.line} />
                {entry.detail && (
                  <code className="mt-1 block truncate font-mono text-xs text-ink-soft">
                    {entry.detail}
                  </code>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}
