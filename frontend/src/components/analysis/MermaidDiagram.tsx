import { useEffect, useId, useState } from 'react'

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function useThemeName(): string {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? 'light')
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setTheme(document.documentElement.dataset.theme ?? 'light'),
    )
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])
  return theme
}

/** Renders a server-built Mermaid diagram. Mermaid is loaded only when needed. */
export function MermaidDiagram({ code, label }: { code: string; label: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '')
  const theme = useThemeName()
  const [svg, setSvg] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    import('mermaid')
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'base',
          fontFamily: 'Geist Variable, ui-sans-serif, sans-serif',
          themeVariables: {
            background: cssVar('--surface'),
            primaryColor: cssVar('--surface'),
            primaryTextColor: cssVar('--ink'),
            primaryBorderColor: cssVar('--ink'),
            lineColor: cssVar('--signal'),
            textColor: cssVar('--ink'),
            fontSize: '14px',
          },
          flowchart: { htmlLabels: false, curve: 'linear' },
        })
        const result = await mermaid.render(`tour-${id}-${theme}`, code)
        if (!cancelled) setSvg(result.svg)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [code, id, theme])

  if (failed) return null
  return (
    <figure className="mermaid-figure overflow-x-auto border-[1.5px] border-ink bg-surface p-4">
      {svg ? (
        <div
          role="img"
          aria-label={label}
          className="mx-auto max-w-md [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      ) : (
        <p className="text-sm text-ink-soft">Drawing the flow.</p>
      )}
    </figure>
  )
}
