# Web interface

The React/TypeScript client is the only conversation interface. Vite proxies the
API during development; Nginx serves the container build and proxies `/api`.

## Conversations

- Completed turns live only in the current page's React state. Follow-ups send
  at most 20 question/answer pairs; no conversation IDs or old tool traces are sent.
- Another window/tab starts empty. Refresh, page exit or New conversation clears
  turns. The app does not write chat history to localStorage, sessionStorage or cookies.
- Page exit aborts the browser request and ignores late responses. This does not
  guarantee cancellation of an already-running model request on the backend.
- Suggested questions populate the composer. Enter sends, Shift+Enter inserts a
  newline, and IME composition does not submit. Pending requests disable duplicate
  submission and the new-chat action.
- Failed questions remain editable; only successful completed turns enter history.

## Sources and failures

The source card identifies online GitHub reading. Policy answers show their
immutable source commit, read count and numbered citations. Selecting a citation
opens its exact excerpt, file path, original line range and server-generated link.
Different passages from one read can have independent numbers. A response with no
citations clears the previous source selection; greetings may have no commit.

Answer and excerpt text are escaped, not interpreted as HTML. Missing model
configuration, offline/source failures and server errors stay visible and can be
retried. A connected health endpoint reports configuration, not verified model
authentication or GitHub availability.

Component tests cover history bounds, isolated windows, resets, late responses,
retry, duplicate prevention, citation selection and offline behavior. Current real
captures and the manual flow are in [the walkthrough](DEMO.md).
