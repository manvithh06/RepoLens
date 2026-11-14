import { useMutation } from '@tanstack/react-query'
import { ArrowRight, Check, LoaderCircle } from 'lucide-react'
import { lazy, Suspense, useState, type FormEvent } from 'react'
import { LayerStack } from '../components/LayerStack'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { analyzeRepositoryStream, type AnalysisStage } from '../lib/api'

const AnalysisResult = lazy(() =>
  import('../components/AnalysisResult').then((module) => ({ default: module.AnalysisResult })),
)

const STEPS = [
  {
    title: 'Check',
    text: 'The repository is looked up on the GitHub API. Private or oversized repositories are rejected before anything is downloaded.',
  },
  {
    title: 'Clone and filter',
    text: 'A shallow copy goes into a temporary folder. Dependencies, binaries, lock files and generated code are dropped, and the folder is deleted when the analysis ends.',
  },
  {
    title: 'Analyse',
    text: 'Manifests, imports and entry points are read as text, never run, and turned into a map of the codebase and a ranked list of improvements.',
  },
  {
    title: 'Explain',
    text: 'A language model reads the key files and writes a guided tour. Every file it cites is checked against the repository before you see it.',
  },
]

const STAGES: { id: AnalysisStage; label: string }[] = [
  { id: 'checking', label: 'Checking the repository on GitHub' },
  { id: 'cloning', label: 'Downloading and filtering files' },
  { id: 'analysing', label: 'Analysing structure, imports and risks' },
]

function StageList({ current }: { current: AnalysisStage | null }) {
  const reached = current ? STAGES.findIndex((stage) => stage.id === current) : -1
  return (
    <ol className="space-y-1.5 text-sm" aria-label="Progress">
      {STAGES.map((stage, position) => {
        const state = position < reached ? 'done' : position === reached ? 'active' : 'waiting'
        return (
          <li
            key={stage.id}
            className={`flex items-center gap-2.5 ${state === 'waiting' ? 'text-ink-faint' : 'text-ink'}`}
            aria-current={state === 'active' ? 'step' : undefined}
          >
            <span className="inline-flex size-4 items-center justify-center" aria-hidden="true">
              {state === 'done' && <Check size={14} className="text-signal" />}
              {state === 'active' && (
                <LoaderCircle size={14} className="animate-spin text-signal motion-reduce:animate-none" />
              )}
              {state === 'waiting' && <span className="size-1.5 bg-line" />}
            </span>
            {stage.label}
            <span className="sr-only">{state === 'done' ? ' (done)' : state === 'active' ? ' (in progress)' : ''}</span>
          </li>
        )
      })}
    </ol>
  )
}

export function Home() {
  useDocumentTitle('RepoLens')
  const [url, setUrl] = useState('')
  const [stage, setStage] = useState<AnalysisStage | null>(null)
  const scan = useMutation({
    mutationFn: (target: string) => {
      setStage(null)
      return analyzeRepositoryStream(target, setStage)
    },
  })

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
            Codebase guide
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
            Paste a GitHub link, get a guided tour of the codebase and a to-do list to make it
            better. Every claim links to the file and line it came from.
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
                {scan.isPending ? 'Analysing' : 'Analyse repository'}
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
            {scan.isPending && <StageList current={stage} />}
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

        <LayerStack scan={scan.isSuccess ? scan.data.scan : null} scanning={scan.isPending} />
      </section>

      {scan.isSuccess ? (
        <Suspense fallback={<p className="text-sm text-ink-soft">Preparing the report.</p>}>
          <AnalysisResult analysis={scan.data} />
        </Suspense>
      ) : (
        <section aria-label="How it works" className="border-t-[1.5px] border-ink pt-10">
          <p className="kicker mb-8">How it works</p>
          <ol className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
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
