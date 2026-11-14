export function LlmSetup({ feature }: { feature: string }) {
  return (
    <div className="border-[1.5px] border-dashed border-ink p-5 text-sm leading-6 text-ink">
      <p className="font-medium">{feature} needs a Hugging Face token.</p>
      <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-ink-soft">
        <li>
          Create a token at{' '}
          <a
            href="https://huggingface.co/settings/tokens"
            target="_blank"
            rel="noreferrer noopener"
            className="text-signal-deep underline"
          >
            huggingface.co/settings/tokens
          </a>{' '}
          with permission to make calls to Inference Providers.
        </li>
        <li>
          Add it to <code className="font-mono text-ink">backend/.env</code> as{' '}
          <code className="font-mono text-ink">HF_TOKEN=your_token</code>.
        </li>
        <li>Restart the backend and analyse the repository again.</li>
      </ol>
      <p className="mt-3 text-ink-soft">Everything else in this report works without it.</p>
    </div>
  )
}
