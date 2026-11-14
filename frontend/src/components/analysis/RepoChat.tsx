import { useMutation } from '@tanstack/react-query'
import { ArrowUp, LoaderCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError, askRepository } from '../../lib/api'
import { useRepoLinks } from '../../lib/repoLinks'
import { sourceUrl } from '../../lib/format'
import type { ChatAnswer, ChatCitation, ChatTurn } from '../../types/api'
import { Notice, Panel } from '../ui'
import { LlmSetup } from './LlmSetup'

interface Message {
  question: string
  answer?: ChatAnswer
  error?: ApiError
}

const SUGGESTIONS = [
  'Where does the program start?',
  'How is configuration loaded?',
  'How are errors handled?',
]

function Snippet({ citation }: { citation: ChatCitation }) {
  const links = useRepoLinks()
  const lines = citation.snippet.split('\n')
  return (
    <div className="mt-2 border-[1.5px] border-ink bg-paper">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-1.5">
        <span className="break-all font-mono text-xs text-ink">
          {citation.path}:{citation.start_line}-{citation.end_line}
          {citation.symbol ? <span className="text-ink-faint"> ({citation.symbol})</span> : null}
        </span>
        {links && (
          <a
            href={`${sourceUrl(links.htmlUrl, links.branch, citation.path)}#L${citation.start_line}-L${citation.end_line}`}
            target="_blank"
            rel="noreferrer noopener"
            className="text-xs text-signal-deep underline"
          >
            Open on GitHub
          </a>
        )}
      </div>
      <pre className="max-h-72 overflow-auto p-3 font-mono text-[0.72rem] leading-5 text-ink">
        {lines.map((line, index) => (
          <div key={index} className="flex">
            <span className="mr-3 inline-block w-8 shrink-0 select-none text-right text-ink-faint">
              {citation.start_line + index}
            </span>
            <span className="whitespace-pre">{line}</span>
          </div>
        ))}
      </pre>
    </div>
  )
}

function CitationList({ items }: { items: ChatCitation[] }) {
  const [open, setOpen] = useState<string | null>(null)
  const active = items.find((item) => item.id === open)
  return (
    <div className="mt-3">
      <ul className="flex flex-wrap gap-2">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              aria-expanded={open === item.id}
              onClick={() => setOpen(open === item.id ? null : item.id)}
              className={`max-w-full break-all rounded-sm border-[1.5px] px-2 py-0.5 text-left font-mono text-[0.7rem] transition-colors ${
                open === item.id
                  ? 'border-signal bg-signal-wash text-ink'
                  : 'border-line text-ink-soft hover:border-ink hover:text-ink'
              }`}
            >
              {item.id} {item.path}:{item.start_line}-{item.end_line}
            </button>
          </li>
        ))}
      </ul>
      {active && <Snippet citation={active} />}
    </div>
  )
}

function AnswerView({ message }: { message: Message }) {
  if (message.error) {
    if (message.error.code === 'llm_not_configured') return <LlmSetup feature="Chat" />
    return <Notice tone="danger">{message.error.message}</Notice>
  }
  const answer = message.answer
  if (!answer) {
    return (
      <p className="flex items-center gap-2 text-sm text-ink-soft" role="status">
        <LoaderCircle size={14} className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
        Searching the code and writing an answer.
      </p>
    )
  }
  if (!answer.answerable) {
    return (
      <div>
        <Notice>{answer.answer}</Notice>
        {answer.related.length > 0 && (
          <>
            <p className="kicker mt-3">Closest code found</p>
            <CitationList items={answer.related} />
          </>
        )}
      </div>
    )
  }
  return (
    <div>
      <p className="whitespace-pre-wrap break-words text-sm leading-6 text-ink">{answer.answer}</p>
      <CitationList items={answer.citations} />
    </div>
  )
}

export function RepoChat({ analysisId, index }: { analysisId: string; index: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')

  const ask = useMutation({
    mutationFn: ({ question, history }: { question: string; history: ChatTurn[] }) =>
      askRepository(analysisId, question, history),
  })

  function send(question: string) {
    const trimmed = question.trim()
    if (!trimmed || ask.isPending) return
    const history: ChatTurn[] = messages.flatMap((message) => [
      { role: 'user' as const, content: message.question },
      ...(message.answer
        ? [{ role: 'assistant' as const, content: message.answer.answer.slice(0, 2000) }]
        : []),
    ]).slice(-6)
    const position = messages.length
    setMessages((current) => [...current, { question: trimmed }])
    setDraft('')
    ask.mutate(
      { question: trimmed, history },
      {
        onSuccess: (answer) =>
          setMessages((current) =>
            current.map((m, i) => (i === position ? { ...m, answer } : m)),
          ),
        onError: (error) =>
          setMessages((current) =>
            current.map((m, i) =>
              i === position
                ? { ...m, error: error instanceof ApiError ? error : new ApiError(0, 'unknown_error', error.message) }
                : m,
            ),
          ),
      },
    )
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    send(draft)
  }

  return (
    <Panel index={index} title="Ask the code" id="chat">
      {messages.length === 0 ? (
        <div className="mb-5">
          <p className="text-sm text-ink-soft">
            Ask a question about this repository. Answers are written only from code found by
            keyword search, cite the exact lines, and say so when the code does not answer it.
          </p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map((suggestion) => (
              <li key={suggestion}>
                <button
                  type="button"
                  onClick={() => send(suggestion)}
                  className="rounded-sm border-[1.5px] border-line px-2.5 py-1 text-sm text-ink-soft hover:border-ink hover:text-ink"
                >
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <ol className="mb-5 space-y-6" aria-live="polite">
          {messages.map((message, position) => (
            <li key={position} className="space-y-2">
              <p className="font-medium text-ink">
                <span className="mr-2 font-mono text-xs text-signal">Q{position + 1}</span>
                {message.question}
              </p>
              <AnswerView message={message} />
            </li>
          ))}
        </ol>
      )}

      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        <label htmlFor="chat-question" className="sr-only">
          Your question
        </label>
        <textarea
          id="chat-question"
          rows={2}
          maxLength={1000}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              send(draft)
            }
          }}
          placeholder="How does a request reach the database?"
          className="min-w-0 flex-1 resize-y rounded-sm border-[1.5px] border-ink bg-surface px-3 py-2 text-sm text-ink outline-none placeholder:text-ink-faint focus:shadow-[3px_3px_0_0_var(--signal)]"
        />
        <button
          type="submit"
          disabled={ask.isPending || draft.trim() === ''}
          aria-label="Ask"
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-sm border-[1.5px] border-ink bg-ink text-paper shadow-[3px_3px_0_0_var(--signal)] disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
        >
          {ask.isPending ? (
            <LoaderCircle size={16} className="animate-spin motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <ArrowUp size={16} aria-hidden="true" />
          )}
        </button>
      </form>
      <p className="mt-3 text-xs text-ink-faint">
        Retrieval is keyword based (BM25). Code and your question are sent to a Hugging Face model.
      </p>
    </Panel>
  )
}
