import { SKIP_LABELS } from '../lib/labels'
import type { RepositoryScan } from '../types/api'

interface Layer {
  label: string
  count: number | null
  kept: boolean
}

const PLACEHOLDER_LAYERS: Layer[] = [
  { label: 'Source files', count: null, kept: true },
  { label: 'Config and manifests', count: null, kept: true },
  { label: 'Documentation', count: null, kept: true },
  { label: 'Skipped', count: null, kept: false },
]

function layersFromScan(scan: RepositoryScan): Layer[] {
  const skipped = Object.entries(scan.skipped)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([reason, count]): Layer => ({
      label: SKIP_LABELS[reason] ?? reason,
      count,
      kept: false,
    }))
  return [{ label: 'Kept for analysis', count: scan.file_count, kept: true }, ...skipped]
}

const GAP_PX = 40

export function LayerStack({
  scan,
  scanning,
}: {
  scan: RepositoryScan | null
  scanning: boolean
}) {
  const layers = scan ? layersFromScan(scan) : PLACEHOLDER_LAYERS
  const sweepTop = (layers.length - 1) * GAP_PX + 16

  return (
    <div>
      <div className="stack-scene h-80" aria-hidden="true">
        <div
          key={scan ? scan.repository.full_name : 'idle'}
          className="stack"
          style={{ ['--sweep-top' as string]: `${sweepTop}px` }}
        >
          <div className="floor" />
          {layers.map((layer, index) => (
            <div
              key={`${layer.label}-${index}`}
              className={`slab ${layer.kept ? 'slab--kept' : 'slab--skipped'}`}
              style={{
                ['--z' as string]: `${index * GAP_PX}px`,
                ['--i' as string]: index,
              }}
            />
          ))}
          {scanning && <div className="scan-plane" />}
        </div>
      </div>

      <ol className="mx-auto mt-2 max-w-sm space-y-2.5 text-sm" aria-label="Layers of the scan">
        {layers
          .map((layer, index) => ({ layer, index }))
          .reverse()
          .map(({ layer, index }) => (
            <li key={`${layer.label}-${index}`} className="flex items-baseline gap-3">
              <span className="font-mono text-[0.7rem] text-ink-faint">
                L{String(index + 1).padStart(2, '0')}
              </span>
              <span
                className={`inline-block size-2.5 shrink-0 translate-y-px border border-ink ${
                  layer.kept ? 'bg-signal' : 'bg-surface'
                }`}
              />
              <span className="text-ink">{layer.label}</span>
              <span className="mb-1 min-w-4 flex-1 self-end border-b border-dotted border-ink-faint" />
              <span className="font-mono text-xs tabular-nums text-ink">
                {layer.count === null ? '..' : layer.count}
              </span>
            </li>
          ))}
      </ol>
    </div>
  )
}
