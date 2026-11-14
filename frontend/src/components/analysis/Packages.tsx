import type { ExternalPackage, Manifest } from '../../types/api'
import { formatCount } from '../../lib/format'
import { BarList, Panel, SourceLink } from '../ui'

export function Packages({
  packages,
  manifests,
  index,
}: {
  packages: ExternalPackage[]
  manifests: Manifest[]
  index: string
}) {
  return (
    <Panel index={index} title="External packages" id="packages">
      <p className="kicker mb-3">Most imported in code</p>
      <BarList
        items={packages.map((item): [string, number] => [
          `${item.name} (${item.ecosystem === 'npm' ? 'npm' : 'Python'})`,
          item.files,
        ])}
        empty="No third party imports were found in Python, JavaScript or TypeScript files."
      />
      <p className="mt-3 text-xs text-ink-faint">Counts are the number of files that import each package.</p>

      <p className="kicker mb-3 mt-8">Declared in manifests</p>
      {manifests.length === 0 ? (
        <p className="text-sm text-ink-soft">No dependency manifests were found.</p>
      ) : (
        <ul className="divide-y divide-dashed divide-line">
          {manifests.map((manifest) => {
            const dev = manifest.dependencies.filter((dep) => dep.dev).length
            return (
              <li key={manifest.path} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2">
                <SourceLink path={manifest.path} />
                {manifest.error ? (
                  <span className="text-xs text-danger-text">{manifest.error}</span>
                ) : (
                  <span className="font-mono text-xs text-ink-soft">
                    {formatCount(manifest.dependencies.length - dev, 'runtime dependency', 'runtime dependencies')}
                    {dev > 0 ? `, ${dev} dev` : ''}
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Panel>
  )
}
