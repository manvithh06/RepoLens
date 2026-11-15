export function LlmSetup({ feature }: { feature: string }) {
  return (
    <div className="border-[1.5px] border-dashed border-line p-5 text-sm leading-6 text-ink-soft">
      <p>
        <span className="font-medium text-ink">AI features are not configured on this server.</span>{' '}
        {feature} needs a language model, so it is switched off here. Everything else in this
        report works without it.
      </p>
      {import.meta.env.DEV && (
        <p className="mt-2 text-xs text-ink-faint">
          For local development, set <code className="font-mono">LLM_BASE_URL</code> and{' '}
          <code className="font-mono">LLM_API_KEY</code> (or <code className="font-mono">HF_TOKEN</code>)
          in <code className="font-mono">backend/.env</code>, then restart the backend.
        </p>
      )}
    </div>
  )
}
