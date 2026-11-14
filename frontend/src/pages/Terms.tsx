import { CONTACT_EMAIL, LAST_UPDATED } from '../config'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

export function Terms() {
  useDocumentTitle('Terms and Conditions | RepoLens')
  return (
    <article className="max-w-2xl space-y-5 text-[0.95rem] leading-7 text-ink">
      <h1 className="font-display text-5xl leading-none">Terms and Conditions</h1>
      <p className="text-ink-soft">Last updated: {LAST_UPDATED}</p>

      <h2 className="pt-2 text-base font-semibold">Using the service</h2>
      <p>
        RepoLens is provided to help you understand public source code. By using it you agree to
        these terms. If you do not agree, do not use the service.
      </p>

      <h2 className="pt-2 text-base font-semibold">Acceptable use</h2>
      <p>
        Only submit URLs of public GitHub repositories that you are allowed to analyse. Do not
        try to disrupt the service, bypass its limits, or use it to access systems other than
        public GitHub repositories.
      </p>

      <h2 className="pt-2 text-base font-semibold">Limits</h2>
      <p>
        To keep the service available, we limit repository size, file counts, processing time and
        the number of simultaneous requests. Requests that exceed these limits may be rejected.
      </p>

      <h2 className="pt-2 text-base font-semibold">No warranty</h2>
      <p>
        The service is provided as is, without warranties of any kind. Results can be incomplete
        or wrong, and you should verify anything important against the repository itself. To the
        extent permitted by law, we are not liable for losses arising from use of the service.
      </p>

      <h2 className="pt-2 text-base font-semibold">Changes</h2>
      <p>We may update these terms. The date at the top shows when they last changed.</p>

      <h2 className="pt-2 text-base font-semibold">Contact</h2>
      <p>
        Questions about these terms can be sent to{' '}
        <a href={`mailto:${CONTACT_EMAIL}`} className="text-signal-deep underline">
          {CONTACT_EMAIL}
        </a>
        .
      </p>
    </article>
  )
}
