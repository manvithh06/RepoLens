import { useMemo } from 'react'
import { SKIP_LABELS } from '../lib/labels'
import { RepoLinksContext } from '../lib/repoLinks'
import type { RepositoryAnalysis } from '../types/api'
import { Architecture } from './analysis/Architecture'
import { EntryPoints } from './analysis/EntryPoints'
import { FileTree } from './analysis/FileTree'
import { GuidedTour } from './analysis/GuidedTour'
import { Improvements } from './analysis/Improvements'
import { Overview } from './analysis/Overview'
import { Packages } from './analysis/Packages'
import { Stack } from './analysis/Stack'
import { BarList, Panel } from './ui'

const SECTIONS = [
  ['overview', 'Overview'],
  ['tour', 'Tour'],
  ['stack', 'Stack'],
  ['entry-points', 'Entry points'],
  ['architecture', 'Architecture'],
  ['improvements', 'Improvements'],
  ['structure', 'Structure'],
  ['packages', 'Packages'],
  ['files', 'Files'],
] as const

type SectionId = (typeof SECTIONS)[number][0]

function number(id: SectionId): string {
  const position = SECTIONS.findIndex(([section]) => section === id) + 1
  return String(position).padStart(2, '0')
}

export function AnalysisResult({ analysis }: { analysis: RepositoryAnalysis }) {
  const { scan } = analysis
  const links = useMemo(
    () => ({ htmlUrl: scan.repository.html_url, branch: scan.repository.default_branch }),
    [scan.repository.html_url, scan.repository.default_branch],
  )
  const entryPaths = useMemo(
    () => new Set(analysis.entry_points.map((entry) => entry.path)),
    [analysis.entry_points],
  )
  const skipped = Object.entries(scan.skipped).map(([reason, count]): [string, number] => [
    SKIP_LABELS[reason] ?? reason,
    count,
  ])

  return (
    <RepoLinksContext value={links}>
      <nav aria-label="Report sections" className="mb-8 overflow-x-auto border-y-[1.5px] border-ink py-2">
        <ol className="flex gap-5 whitespace-nowrap text-sm">
          {SECTIONS.map(([id, label]) => (
            <li key={id}>
              <a href={`#${id}`} className="text-ink-soft hover:text-ink hover:underline">
                <span className="mr-1.5 font-mono text-xs text-signal">{number(id)}</span>
                {label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <div className="space-y-8">
        <Overview analysis={analysis} index={number('overview')} />
        <GuidedTour analysisId={analysis.analysis_id} index={number('tour')} />
        <Stack frameworks={analysis.frameworks} index={number('stack')} />
        <EntryPoints entries={analysis.entry_points} index={number('entry-points')} />
        <Architecture architecture={analysis.architecture} graph={analysis.graph} index={number('architecture')} />
        <Improvements findings={analysis.improvements} index={number('improvements')} />
        <div className="grid items-start gap-8 lg:grid-cols-2">
          <FileTree tree={analysis.tree} entryPaths={entryPaths} index={number('structure')} />
          <Packages
            packages={analysis.graph.external_packages}
            manifests={analysis.manifests}
            index={number('packages')}
          />
        </div>
        <Panel index={number('files')} title="Files" id="files">
          <div className="grid gap-8 md:grid-cols-2">
            <div>
              <p className="kicker mb-3">Types kept</p>
              <BarList items={Object.entries(scan.extensions)} />
            </div>
            <div>
              <p className="kicker mb-3">Skipped</p>
              <BarList items={skipped} hatched empty="Nothing was skipped." />
            </div>
          </div>
        </Panel>
      </div>
    </RepoLinksContext>
  )
}
