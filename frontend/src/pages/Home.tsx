import { useMutation } from '@tanstack/react-query'
import { ArrowRight, LoaderCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { LayerStack } from '../components/LayerStack'
import { ScanResult } from '../components/ScanResult'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { scanRepository } from '../lib/api'

const STEPS = [
  {
    title: 'Check',
    text: 'The repository is looked up on the GitHub API. Private or oversized repositories are rejected before anything is downloaded.',
  },
  {
    title: 'Clone',
    text: 'A shallow copy of the default branch goes into a temporary folder that is deleted when the scan ends.',
  },
  {
    title: 'Filter',
    text: 'Dependencies, binaries, lock files, generated code and symlinks are dropped. Everything else is kept and counted.',
  },
]

export function Home() {
  useDocumentTitle('RepoLens')
  const [url, setUrl] = useState('')
  const scan = useMutation({ mutationFn: scanRepository })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = url.trim()
    if (trimmed) scan.mutate(trimmed)
  }

  return (
    <div className="space-y-20">
      <section className="grid items-center gap-14 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="kicker reveal mb-6 flex items-center gap-3">
            <span className="h-px w-8 bg-signal" aria-hidden="true" />
            Repository scanner
          </p>
          <h1
            className="reveal font-display text-[3.4rem] leading-[0.95] tracking-[-0.01em] text-ink sm:text-[5.2rem]"
            style={{ ['--d' as string]: 1 }}
          >
            See what is <em className="text-signal">inside</em> a repository before you read it.
          </h1>
          <p
            className="reveal mt-7 max-w-lg text-lg leading-relaxed text-ink-soft"
            style={{ ['--d' as string]: 2 }}
          >
            Paste a public GitHub URL. RepoLens pulls a temporary copy, strips out the noise, and
            shows you the layers it kept and skipped.
          </p>

          <form
            onSubmit={handleSubmit}
            className="reveal mt-10"
            style={{ ['--d' as string]: 3 }}
          >
            <label htmlFor="repo-url" className="kicker mb-2.5 block">
              Repository URL
            </label>
            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                id="repo-url"
                type="text"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://github.com/owner/repository"
                autoComplete="off"
                spellCheck={false}
                className="min-w-0 flex-1 rounded-sm border-[1.5px] border-ink bg-surface px-4 py-3.5 font-mono text-sm text-ink outline-none transition-shadow placeholder:text-ink-faint focus:shadow-[4px_4px_0_0_var(--signal)]"
              />
              <button
                type="submit"
                disabled={scan.isPending || url.trim() === ''}
                className="group inline-flex items-center justify-center gap-2.5 rounded-sm border-[1.5px] border-ink bg-ink px-6 py-3.5 text-sm font-medium text-paper shadow-[4px_4px_0_0_var(--signal)] transition-[transform,box-shadow] active:translate-x-[3px] active:translate-y-[3px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
              >
                {scan.isPending ? (
                  <LoaderCircle
                    size={16}
                    className="animate-spin motion-reduce:animate-none"
                    aria-hidden="true"
                  />
                ) : null}
                {scan.isPending ? 'Scanning' : 'Scan repository'}
                {scan.isPending ? null : (
                  <ArrowRight
                    size={16}
                    className="transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                )}
              </button>
            </div>
          </form>

          <div aria-live="polite" className="mt-4 min-h-6 text-sm">
            {scan.isPending && (
              <p className="text-ink-soft">
                Downloading and filtering. Large repositories can take up to two minutes.
              </p>
            )}
            {scan.isError && (
              <div
                role="alert"
                className="border-[1.5px] border-danger-border bg-danger-bg p-3 text-danger-text"
              >
                {scan.error.message}
              </div>
            )}
          </div>
        </div>

        <LayerStack scan={scan.isSuccess ? scan.data : null} scanning={scan.isPending} />
      </section>

      {scan.isSuccess ? (
        <ScanResult scan={scan.data} />
      ) : (
        <section aria-label="How a scan works" className="border-t-[1.5px] border-ink pt-10">
          <p className="kicker mb-8">How a scan works</p>
          <ol className="grid gap-10 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <p className="font-display text-6xl leading-none text-signal">{index + 1}</p>
                <h3 className="mt-4 text-lg font-medium text-ink">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-ink-soft">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}
