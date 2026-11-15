import { useQuery } from '@tanstack/react-query'
import { LoaderCircle, RotateCcw, TriangleAlert } from 'lucide-react'
import { fetchTour, isNotConfigured, isRetryable } from '../../lib/api'
import { formatCount } from '../../lib/format'
import type { Citation, Tour } from '../../types/api'
import { Notice, Panel, SourceLink } from '../ui'
import { LlmSetup } from './LlmSetup'
import { MermaidDiagram } from './MermaidDiagram'

function Citations({ items }: { items: Citation[] }) {
  if (items.length === 0) return null
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
      {items.map((item) => (
        <li key={`${item.path}:${item.line ?? ''}`} className="min-w-0">
          {item.is_dir ? (
            <span className="break-all font-mono text-xs text-ink-soft">{item.path}/</span>
          ) : (
            <SourceLink path={item.path} line={item.line} />
          )}
        </li>
      ))}
    </ul>
  )
}

function TourBody({ tour }: { tour: Tour }) {
  return (
    <div className="space-y-10">
      {tour.overview && (
        <div>
          {!tour.overview.verified && (
            <div className="mb-3">
              <Notice>
                This summary could not be checked: none of the files it mentioned exist in the
                repository. Read it with care.
              </Notice>
            </div>
          )}
          <p className="max-w-3xl font-display text-2xl leading-snug text-ink sm:text-[1.7rem]">
            {tour.overview.text}
          </p>
          <Citations items={tour.overview.citations} />
        </div>
      )}

      {tour.steps.length > 0 && (
        <div>
          <h3 className="kicker mb-4">How it works</h3>
          <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr]">
            <ol className="space-y-5">
              {tour.steps.map((step, index) => (
                <li key={step.title} className="grid grid-cols-[2.2rem_1fr] gap-x-3">
                  <span className="font-display text-3xl leading-none text-signal">{index + 1}</span>
                  <div className="min-w-0">
                    <p className="font-medium text-ink">{step.title}</p>
                    <p className="mt-1 text-sm leading-6 text-ink-soft">{step.detail}</p>
                    <Citations items={step.citations} />
                  </div>
                </li>
              ))}
            </ol>
            {tour.diagram && (
              <MermaidDiagram
                code={tour.diagram}
                label={`Flow: ${tour.steps.map((step) => step.title).join(', then ')}`}
              />
            )}
          </div>
        </div>
      )}

      {tour.modules.length > 0 && (
        <div>
          <h3 className="kicker mb-4">Module by module</h3>
          <ul className="grid gap-4 sm:grid-cols-2">
            {tour.modules.map((module) => (
              <li key={`${module.path}-${module.name}`} className="border-[1.5px] border-line p-4">
                <p className="font-medium text-ink">{module.name}</p>
                <p className="break-all font-mono text-xs text-ink-faint">{module.path}</p>
                <p className="mt-2 text-sm leading-6 text-ink-soft">{module.summary}</p>
                <Citations items={module.citations} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {tour.start_here.length > 0 && (
        <div>
          <h3 className="kicker mb-4">Start reading here</h3>
          <ol className="space-y-3">
            {tour.start_here.map((item, index) => (
              <li key={item.path} className="grid grid-cols-[2.2rem_1fr] gap-x-3">
                <span className="font-mono text-sm text-signal">{String(index + 1).padStart(2, '0')}</span>
                <div className="min-w-0">
                  <SourceLink path={item.path} className="text-sm" />
                  <p className="mt-0.5 text-sm text-ink-soft">{item.reason}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className="border-t border-dashed border-line pt-4 text-xs leading-5 text-ink-faint">
        Written by the language model {tour.model} after reading{' '}
        {formatCount(tour.files_read.length, 'key file')}. Every file and line it cited was checked
        against the repository
        {tour.dropped_claims > 0
          ? `, and ${formatCount(tour.dropped_claims, 'statement')} whose citations did not check out ${tour.dropped_claims === 1 ? 'was' : 'were'} removed`
          : ''}
        . It can still misread code, so follow the links.
        {tour.cached ? ' Reused from an earlier tour of the same commit.' : ''}
      </p>
    </div>
  )
}

export function GuidedTour({ analysisId, index }: { analysisId: string; index: string }) {
  const tour = useQuery({
    queryKey: ['tour', analysisId],
    queryFn: () => fetchTour(analysisId),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
  const notConfigured = isNotConfigured(tour.error)

  return (
    <Panel index={index} title="Guided tour" id="tour">
      {tour.isPending && (
        <div className="flex items-start gap-3 text-sm text-ink-soft" role="status">
          <LoaderCircle size={16} className="mt-0.5 shrink-0 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          <p>
            Summarising the key files, then their folders, then the whole repository. This usually
            takes under a minute. The rest of the report is ready below.
          </p>
        </div>
      )}
      {notConfigured && <LlmSetup feature="The guided tour" />}
      {tour.isError && !notConfigured && (
        <div role="alert" className="space-y-3">
          <Notice tone="danger">
            <span className="flex items-start gap-2">
              <TriangleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              {tour.error.message}
            </span>
          </Notice>
          {isRetryable(tour.error) && (
            <button
              type="button"
              onClick={() => tour.refetch()}
              disabled={tour.isFetching}
              className="inline-flex items-center gap-2 rounded-sm border-[1.5px] border-ink px-3 py-1.5 text-sm text-ink hover:bg-ink hover:text-paper disabled:cursor-wait disabled:opacity-50"
            >
              <RotateCcw size={14} aria-hidden="true" />
              {tour.isFetching ? 'Trying again' : 'Try again'}
            </button>
          )}
        </div>
      )}
      {tour.isSuccess && <TourBody tour={tour.data} />}
    </Panel>
  )
}
