import { CONTACT_EMAIL, LAST_UPDATED } from '../config'
import { useDocumentTitle } from '../hooks/useDocumentTitle'

export function Privacy() {
  useDocumentTitle('Privacy Policy | RepoLens')
  return (
    <article className="max-w-2xl space-y-5 text-[0.95rem] leading-7 text-ink">
      <h1 className="font-display text-5xl leading-none">Privacy Policy</h1>
      <p className="text-ink-soft">Last updated: {LAST_UPDATED}</p>

      <h2 className="pt-2 text-base font-semibold">What RepoLens does</h2>
      <p>
        You enter the URL of a public GitHub repository. Our server fetches that repository,
        analyses its files, and returns the result to your browser.
      </p>

      <h2 className="pt-2 text-base font-semibold">What we collect</h2>
      <p>
        The repository URL you submit is sent to our server and to the GitHub API so the
        repository can be checked and downloaded. Like most web servers, ours records technical
        request information in logs, such as the time of the request, the requested path and
        error details. To prevent abuse, your IP address is held in memory for up to ten minutes to
        count requests. It is not stored. We do not require an account and we do not ask for your name or email to
        use the tool.
      </p>

      <h2 className="pt-2 text-base font-semibold">What happens to the repository</h2>
      <p>
        The repository is downloaded into a temporary folder on our server and deleted when the
        analysis finishes. Only public repositories are supported. Do not submit private code.
      </p>
      <p>
        So that the guided tour and chat can work after the download is deleted, excerpts of the
        repository's text files (split into small sections) and the list of its file names are
        kept in the server's memory for up to one hour, then discarded. They are never written to
        disk or a database. Values that look like passwords or keys are masked, and .env files are
        left out.
      </p>

      <h2 className="pt-2 text-base font-semibold">Language model processing</h2>
      <p>
        The guided tour and the chat send repository content to a language model hosted through
        Hugging Face Inference Providers. For the tour this is up to twelve key files, such as the
        README, entry points and the most imported modules. For chat it is the code sections that
        best match your question, together with the question itself and your earlier questions in
        the same conversation. Hugging Face and the provider that runs the model process this data
        under their own terms and privacy policies. The rest of the report (structure, stack,
        architecture and improvements) is produced on our server without a language model.
      </p>

      <h2 className="pt-2 text-base font-semibold">Cookies and tracking</h2>
      <p>RepoLens does not use advertising cookies or third-party trackers.</p>

      <h2 className="pt-2 text-base font-semibold">Third parties</h2>
      <p>
        We rely on GitHub to supply repositories, on Hugging Face and its inference providers to
        run the language model, and on our hosting provider to run the service. Their own privacy
        policies apply to the data they handle.
      </p>

      <h2 className="pt-2 text-base font-semibold">Contact</h2>
      <p>
        Questions about this policy can be sent to{' '}
        <a href={`mailto:${CONTACT_EMAIL}`} className="text-signal-deep underline">
          {CONTACT_EMAIL}
        </a>
        .
      </p>
    </article>
  )
}
