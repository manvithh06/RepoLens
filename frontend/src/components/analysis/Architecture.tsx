import { Graph, layout } from '@dagrejs/dagre'
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { TriangleAlert } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { formatBytes, formatCount, splitPath } from '../../lib/format'
import type { ArchitectureGraph, Cycle, ImportGraph, ModuleKind } from '../../types/api'
import { Checkbox, EmptyState, Notice, Panel, SourceLink, Toggle } from '../ui'

type Mode = 'folders' | 'files'

interface Item {
  id: string
  label: string
  sub: string
  kind: ModuleKind
}

interface Link {
  source: string
  target: string
  weight: number
}

interface ModuleData extends Record<string, unknown> {
  label: string
  sub: string
  kind: ModuleKind
  state: 'normal' | 'selected' | 'dim'
}

type ModuleNode = Node<ModuleData, 'module'>

const SIZE: Record<Mode, { width: number; height: number }> = {
  folders: { width: 200, height: 54 },
  files: { width: 190, height: 48 },
}

function ModuleBox({ data }: NodeProps<ModuleNode>) {
  return (
    <div
      className={`graph-node graph-node--${data.kind} ${
        data.state === 'selected' ? 'graph-node--selected' : ''
      } ${data.state === 'dim' ? 'graph-node--dim' : ''} flex flex-col justify-center px-3`}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <span className="truncate font-mono text-[0.72rem] text-ink">{data.label}</span>
      <span className="truncate text-[0.68rem] text-ink-faint">{data.sub}</span>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  )
}

const nodeTypes = { module: ModuleBox }

function buildItems(
  mode: Mode,
  architecture: ArchitectureGraph,
  graph: ImportGraph,
): { items: Item[]; links: Link[] } {
  if (mode === 'folders') {
    return {
      items: architecture.modules.map((module) => ({
        id: module.id,
        label: module.label,
        sub: `${formatCount(module.file_count, 'file')}, ${formatBytes(module.size)}`,
        kind: module.kind,
      })),
      links: architecture.edges,
    }
  }
  return {
    items: graph.nodes.map((node) => {
      const [folder, file] = splitPath(node.id)
      return { id: node.id, label: file, sub: folder || '(root)', kind: node.kind }
    }),
    links: graph.edges.map((edge) => ({ ...edge, weight: 1 })),
  }
}

function layoutNodes(items: Item[], links: Link[], mode: Mode): Map<string, { x: number; y: number }> {
  const { width, height } = SIZE[mode]
  const graph = new Graph()
  graph.setGraph({ rankdir: 'LR', nodesep: 18, ranksep: 70, marginx: 16, marginy: 16 })
  graph.setDefaultEdgeLabel(() => ({}))
  for (const item of items) graph.setNode(item.id, { width, height })
  for (const link of links) graph.setEdge(link.source, link.target)
  layout(graph)
  const positions = new Map<string, { x: number; y: number }>()
  for (const item of items) {
    const point = graph.node(item.id)
    positions.set(item.id, { x: point.x - width / 2, y: point.y - height / 2 })
  }
  return positions
}

function CycleList({ cycles }: { cycles: Cycle[] }) {
  if (cycles.length === 0) return null
  return (
    <div className="mt-6">
      <Notice>
        <p className="mb-3 flex items-start gap-2 font-medium">
          <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          {formatCount(cycles.length, 'import cycle')} found. Files in a cycle import each other,
          so none of them can be understood or tested alone.
        </p>
        <ol className="space-y-2">
          {cycles.map((cycle) => (
            <li key={cycle.files.join('|')} className="flex flex-wrap items-baseline gap-x-1.5 gap-y-1">
              {[...cycle.files, cycle.files[0]].map((file, position) => (
                <span key={`${file}-${position}`} className="inline-flex items-baseline gap-1.5">
                  {position > 0 && <span aria-label="imports">→</span>}
                  <SourceLink path={file} />
                </span>
              ))}
              {cycle.group_size > cycle.files.length && (
                <span className="text-xs">
                  ({cycle.group_size} files are tangled together in total)
                </span>
              )}
            </li>
          ))}
        </ol>
      </Notice>
    </div>
  )
}

function Details({
  item,
  mode,
  links,
  byId,
  onSelect,
}: {
  item: Item
  mode: Mode
  links: Link[]
  byId: Map<string, Item>
  onSelect: (id: string) => void
}) {
  const outgoing = links.filter((link) => link.source === item.id)
  const incoming = links.filter((link) => link.target === item.id)
  const list = (title: string, entries: Link[], key: 'source' | 'target') => (
    <div className="min-w-0">
      <p className="kicker mb-2">
        {title} ({entries.length})
      </p>
      {entries.length === 0 ? (
        <p className="text-sm text-ink-faint">None</p>
      ) : (
        <ul className="max-h-48 space-y-1 overflow-auto pr-1">
          {entries.map((link) => {
            const other = byId.get(link[key])
            return (
              <li key={link[key]} className="flex items-baseline justify-between gap-2">
                <button
                  type="button"
                  onClick={() => onSelect(link[key])}
                  className="min-w-0 truncate text-left font-mono text-xs text-ink hover:text-signal hover:underline"
                >
                  {mode === 'files' ? link[key] : (other?.label ?? link[key])}
                </button>
                {mode === 'folders' && (
                  <span className="shrink-0 font-mono text-[0.7rem] text-ink-faint">
                    {formatCount(link.weight, 'import')}
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
  return (
    <div className="mt-4 border-[1.5px] border-ink bg-paper p-4" aria-live="polite">
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        {mode === 'files' ? (
          <SourceLink path={item.id} className="text-sm" />
        ) : (
          <span className="break-all font-mono text-sm text-ink">{item.label}</span>
        )}
        <span className="text-xs text-ink-soft">{mode === 'folders' ? item.sub : null}</span>
        {item.kind !== 'source' && <span className="kicker border border-line px-1.5">{item.kind}</span>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {list(mode === 'folders' ? 'Depends on' : 'Imports', outgoing, 'target')}
        {list(mode === 'folders' ? 'Used by' : 'Imported by', incoming, 'source')}
      </div>
    </div>
  )
}

export function Architecture({
  architecture,
  graph,
  index,
}: {
  architecture: ArchitectureGraph
  graph: ImportGraph
  index: string
}) {
  const [mode, setMode] = useState<Mode>('folders')
  const [showAll, setShowAll] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [flow, setFlow] = useState<ReactFlowInstance<ModuleNode, Edge> | null>(null)

  const view = useMemo(() => {
    const { items, links } = buildItems(mode, architecture, graph)
    let visible = showAll ? items : items.filter((item) => item.kind === 'source')
    const ids = new Set(visible.map((item) => item.id))
    const visibleLinks = links.filter((link) => ids.has(link.source) && ids.has(link.target))
    let isolated = 0
    if (mode === 'files') {
      const linked = new Set(visibleLinks.flatMap((link) => [link.source, link.target]))
      isolated = visible.filter((item) => !linked.has(item.id)).length
      visible = visible.filter((item) => linked.has(item.id))
    }
    const hiddenByKind = items.length - (showAll ? items.length : items.filter((i) => i.kind === 'source').length)
    return {
      items: visible,
      links: visibleLinks,
      positions: layoutNodes(visible, visibleLinks, mode),
      byId: new Map(visible.map((item) => [item.id, item])),
      hiddenByKind,
      isolated,
    }
  }, [mode, showAll, architecture, graph])

  const active = selected && view.byId.has(selected) ? selected : null
  const neighbours = useMemo(() => {
    if (!active) return null
    const set = new Set([active])
    for (const link of view.links) {
      if (link.source === active) set.add(link.target)
      if (link.target === active) set.add(link.source)
    }
    return set
  }, [active, view.links])

  // Bring the selection and its neighbours into view; without a selection, show everything.
  useEffect(() => {
    if (!flow) return
    const ids = neighbours ? [...neighbours].map((id) => ({ id })) : undefined
    void flow.fitView({ nodes: ids, padding: 0.2, maxZoom: 1, duration: 0 })
  }, [flow, neighbours])

  const nodes: ModuleNode[] = view.items.map((item) => ({
    id: item.id,
    type: 'module',
    position: view.positions.get(item.id) ?? { x: 0, y: 0 },
    data: {
      label: item.label,
      sub: item.sub,
      kind: item.kind,
      state: item.id === active ? 'selected' : neighbours && !neighbours.has(item.id) ? 'dim' : 'normal',
    },
    style: SIZE[mode],
    ariaLabel: `${item.label}, ${item.sub}`,
  }))

  const maxWeight = Math.max(1, ...view.links.map((link) => link.weight))
  const edges: Edge[] = view.links.map((link) => {
    const lit = active !== null && (link.source === active || link.target === active)
    const colour = lit ? 'var(--signal)' : 'var(--ink-faint)'
    return {
      id: `${link.source}->${link.target}`,
      source: link.source,
      target: link.target,
      zIndex: lit ? 1 : 0,
      style: {
        stroke: colour,
        strokeWidth: lit ? 2.25 : 1 + (1.5 * link.weight) / maxWeight,
        opacity: active && !lit ? 0.15 : 1,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: colour, width: 16, height: 16 },
      focusable: false,
    }
  })

  const selectedItem = active ? view.byId.get(active) : undefined
  const totalItems = mode === 'folders' ? architecture.modules.length : graph.nodes.length

  return (
    <Panel
      index={index}
      title="Architecture"
      id="architecture"
      action={
        <Toggle
          label="Graph level"
          value={mode}
          onChange={(value) => {
            setMode(value as Mode)
            setSelected(null)
          }}
          options={[
            { value: 'folders', label: 'Folders' },
            { value: 'files', label: 'Files' },
          ]}
        />
      }
    >
      {totalItems === 0 ? (
        <EmptyState>No Python, JavaScript or TypeScript files were found, so there is no import graph to draw.</EmptyState>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <Checkbox checked={showAll} onChange={setShowAll}>
              Show tests and examples
            </Checkbox>
            <label className="flex min-w-0 items-center gap-2 text-sm text-ink-soft">
              <span className="shrink-0">Focus</span>
              <select
                value={active ?? ''}
                onChange={(event) => setSelected(event.target.value || null)}
                className="min-w-0 max-w-56 rounded-sm border-[1.5px] border-ink bg-surface px-2 py-1 font-mono text-xs text-ink"
              >
                <option value="">Nothing selected</option>
                {view.items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {mode === 'files' ? item.id : item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {view.items.length === 0 ? (
            <EmptyState>
              Nothing to draw with the current filters. Try showing tests and examples.
            </EmptyState>
          ) : (
            <div className="graph-canvas h-[440px] w-full overflow-hidden border-[1.5px] border-ink sm:h-[540px]">
              <ReactFlow<ModuleNode, Edge>
                key={`${mode}-${showAll}`}
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
                minZoom={0.15}
                maxZoom={2}
                nodesDraggable={false}
                nodesConnectable={false}
                zoomOnScroll={false}
                preventScrolling={false}
                onInit={setFlow}
                onNodeClick={(_, node) => setSelected(node.id === active ? null : node.id)}
                onPaneClick={() => setSelected(null)}
              >
                <Background gap={24} size={1} />
                <Controls showInteractive={false} />
              </ReactFlow>
            </div>
          )}

          {selectedItem ? (
            <Details
              item={selectedItem}
              mode={mode}
              links={view.links}
              byId={view.byId}
              onSelect={setSelected}
            />
          ) : (
            <p className="mt-3 text-xs text-ink-faint">
              Select a box to light up what it imports and what imports it. Arrows point from the
              importer to the imported.
            </p>
          )}

          <ul className="mt-4 space-y-1 text-xs text-ink-soft">
            {view.items.length > 1 && view.links.length === 0 && (
              <li>No imports cross between the {mode === 'folders' ? 'folders' : 'files'} shown here.</li>
            )}
            {mode === 'folders' && architecture.depth > 0 && (
              <li>Folders are grouped {formatCount(architecture.depth, 'level')} deep. Line weight shows how many imports cross between two folders.</li>
            )}
            {!showAll && view.hiddenByKind > 0 && (
              <li>{formatCount(view.hiddenByKind, mode === 'folders' ? 'test or example folder' : 'test or example file')} hidden.</li>
            )}
            {mode === 'files' && view.isolated > 0 && (
              <li>{formatCount(view.isolated, 'file')} with no local imports in either direction not shown.</li>
            )}
            {mode === 'files' && graph.truncated && (
              <li>Showing the {graph.nodes.length} most connected of {graph.total_files} script files.</li>
            )}
            {graph.parse_errors > 0 && (
              <li>{formatCount(graph.parse_errors, 'Python file')} could not be parsed and has no edges.</li>
            )}
          </ul>
        </>
      )}

      <CycleList cycles={graph.cycles} />
    </Panel>
  )
}
