import { ChevronRight, FileText, Folder } from 'lucide-react'
import { useState } from 'react'
import { formatBytes, formatCount, sourceUrl } from '../../lib/format'
import { useRepoLinks } from '../../lib/repoLinks'
import type { TreeNode } from '../../types/api'
import { Panel } from '../ui'

function TreeRow({
  node,
  depth,
  entryPaths,
  initiallyOpen,
}: {
  node: TreeNode
  depth: number
  entryPaths: Set<string>
  initiallyOpen: boolean
}) {
  const [open, setOpen] = useState(initiallyOpen)
  const links = useRepoLinks()
  const indent = { paddingLeft: `${depth * 14}px` }

  if (!node.is_dir) {
    const isEntry = entryPaths.has(node.path)
    return (
      <li>
        <div style={indent} className="flex min-w-0 items-center gap-1.5 py-0.5 pl-5">
          <FileText size={13} className="shrink-0 text-ink-faint" aria-hidden="true" />
          {links ? (
            <a
              href={sourceUrl(links.htmlUrl, links.branch, node.path)}
              target="_blank"
              rel="noreferrer noopener"
              className={`min-w-0 truncate hover:underline ${isEntry ? 'text-signal-deep' : 'text-ink'}`}
            >
              {node.name}
            </a>
          ) : (
            <span className={`min-w-0 truncate ${isEntry ? 'text-signal-deep' : 'text-ink'}`}>
              {node.name}
            </span>
          )}
          {isEntry && (
            <span className="kicker shrink-0 border border-signal px-1 text-[0.6rem] text-signal-deep">
              entry
            </span>
          )}
          <span className="ml-auto shrink-0 pl-2 text-[0.68rem] text-ink-faint">
            {formatBytes(node.size)}
          </span>
        </div>
      </li>
    )
  }

  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        style={indent}
        className="flex w-full min-w-0 items-center gap-1.5 py-0.5 text-left hover:text-signal"
      >
        <ChevronRight
          size={14}
          className={`shrink-0 text-ink-faint transition-transform motion-reduce:transition-none ${open ? 'rotate-90' : ''}`}
          aria-hidden="true"
        />
        <Folder size={13} className="shrink-0 text-ink-soft" aria-hidden="true" />
        <span className="min-w-0 truncate text-ink">{node.name}</span>
        <span className="ml-auto shrink-0 pl-2 text-[0.68rem] text-ink-faint">
          {formatCount(node.file_count, 'file')}
        </span>
      </button>
      {open && (
        <ul>
          {node.children.map((child) => (
            <TreeRow
              key={child.path}
              node={child}
              depth={depth + 1}
              entryPaths={entryPaths}
              initiallyOpen={false}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

export function FileTree({
  tree,
  entryPaths,
  index,
}: {
  tree: TreeNode
  entryPaths: Set<string>
  index: string
}) {
  return (
    <Panel index={index} title="Structure" id="structure">
      <ul className="max-h-[28rem] overflow-auto pr-1 font-mono text-[0.78rem] leading-6">
        {tree.children.map((child) => (
          <TreeRow
            key={child.path}
            node={child}
            depth={0}
            entryPaths={entryPaths}
            initiallyOpen={child.is_dir && tree.children.length <= 12 && child.file_count <= 60}
          />
        ))}
      </ul>
      <p className="mt-4 text-xs text-ink-faint">
        Kept files only. Files marked entry are where the program starts.
      </p>
    </Panel>
  )
}
