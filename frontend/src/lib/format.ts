export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kilobytes = bytes / 1024
  if (kilobytes < 1024) return `${kilobytes.toFixed(1)} KB`
  return `${(kilobytes / 1024).toFixed(1)} MB`
}

export function formatCount(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`
}

/** Link to a file (and line) on GitHub at the analysed branch. */
export function sourceUrl(htmlUrl: string, branch: string, path: string, line?: number | null) {
  const encoded = path.split('/').map(encodeURIComponent).join('/')
  return `${htmlUrl}/blob/${encodeURIComponent(branch)}/${encoded}${line ? `#L${line}` : ''}`
}

export function splitPath(path: string): [string, string] {
  const cut = path.lastIndexOf('/')
  return cut === -1 ? ['', path] : [path.slice(0, cut + 1), path.slice(cut + 1)]
}
