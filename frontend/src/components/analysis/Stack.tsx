import type { Framework, FrameworkCategory } from '../../types/api'
import { EmptyState, Panel, SourceLink } from '../ui'

const ORDER: FrameworkCategory[] = [
  'Frontend',
  'Backend',
  'Data and storage',
  'Machine learning and AI',
  'Testing',
  'Build and tooling',
  'Deployment and CI',
]

export function Stack({ frameworks, index }: { frameworks: Framework[]; index: string }) {
  const groups = ORDER.map((category) => ({
    category,
    items: frameworks.filter((framework) => framework.category === category),
  })).filter((group) => group.items.length > 0)

  return (
    <Panel index={index} title="Detected stack" id="stack">
      {groups.length === 0 ? (
        <EmptyState>
          No known frameworks or tools were found in the manifests or configuration files.
        </EmptyState>
      ) : (
        <div className="grid gap-x-8 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((group) => (
            <div key={group.category} className="min-w-0">
              <h3 className="mb-3 border-b-[1.5px] border-ink pb-1.5 text-sm font-medium text-ink">
                {group.category}
              </h3>
              <ul className="space-y-3">
                {group.items.map((framework) => (
                  <li key={framework.name} className="min-w-0">
                    <p className="text-sm text-ink">{framework.name}</p>
                    <SourceLink
                      path={framework.evidence[0].path}
                      line={framework.evidence[0].line}
                      className="text-[0.7rem]"
                    />
                    {framework.evidence.length > 1 && (
                      <span className="ml-1.5 font-mono text-[0.7rem] text-ink-faint">
                        +{framework.evidence.length - 1}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <p className="mt-6 text-xs text-ink-faint">
        Found from declared dependencies and well-known files. Each item links to the line that
        shows it.
      </p>
    </Panel>
  )
}
