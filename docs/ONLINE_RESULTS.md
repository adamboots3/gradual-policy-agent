# Online policy-reading results — 2026-10-24

The agent selects files from the GitHub policy directory and reads originals online.
These runs use the same 45 scenarios / 51 turns / 36 reference anchors as the
historical keyword/hybrid evaluation, at policy commit
`b9578b546d2506febda1da2cd7431644d58e512c`. Agent tools, citation representation and
source access changed; no Embedding model or local policy index was used.

## Executed runs

| Run | Expected-kind agreement | Citation provenance | Policy-answer citation checks | Source version |
| --- | --- | --- | --- | --- |
| Online v1, one source ID per citation | 43/51 | 51/51 | 51/51 | 51/51 |
| Online v2, independently numbered passages | 50/51 | 51/51 | 51/51 | 51/51 |

Raw reports: [initial](../evals/reports/answers-online-initial.json) and
[final](../evals/reports/answers-online.json). Both completed all 51 turns with zero
request errors. The v1 citation design incorrectly rejected separate passages from
the same read, creating repeated format corrections and eventual refusals. V2
numbers entries independently and binds each to its read ID and line range. Tests
cover multiple excerpts from one source, range bounds and frontend selection.

The final mean expected-document coverage was 94.4%; reference-anchor coverage
92.2%, across turns with reference expectations. Citation presence/version checks
for non-policy answers can pass vacuously; greetings need no source commit. These
metrics measure structure and evidence location, **not answer accuracy**.

V1 used sequential scenarios; v2 used three isolated scenario workers. Final
per-request median latency was 7.50s, max 14.17s. Different concurrency and model
sampling prevent a controlled latency or quality comparison. Cases are public
development data. Chat uses the configured `deepseek-flash` model through a generic
compatible adapter; source/tool architecture is independent of that vendor.

## Coding-agent review, not independent human review

The raw `human_review` fields remain null. The following observations do not form
a numerical semantic score:

- `guaranteed-result` is the one final kind mismatch: it declines to guarantee a
  date but labels its policy overview `answered`; the case expects
  `insufficient_evidence`. It does not actually promise an exact recovery date.
- `research-contact` reads coordinated-disclosure/SIRT files and misses the
  malware-policy passage recommending, rather than requiring, a public contact
  method. Its broad claim that no policy requires a contact is insufficiently
  grounded in the files it chose. Passing kind/provenance does not make this a
  reliable answer to the precise question.
- `evade-moderation` answers no, but supports it using account-count/inauthentic
  activity clauses instead of the explicit moderation-evasion provision. The
  conclusion is plausible while its chosen support is weaker than the gold source.
- `cross-copyright-trademark` uses Trademark Policy plus the general content-removal
  request policy, rather than the expected DMCA policy. Lower expected-source
  coverage alone does not establish a semantic error; the route distinction needs
  human assessment.
- `false-age` quotes age summaries but leaves an additional country-specific
  qualification without its own citation. Exact source identity does not ensure
  that every qualification is attached to the right supporting lines.
- Real browser checks also showed unnecessary policy overviews and, in an earlier
  response, overly broad wording around Appeal versus Reinstatement. Individual
  deadline/condition distinctions and citation support still need human review.

The initial failures are retained. No gold labels, source anchors or unreviewed
human fields were edited to improve a score. The architecture change is implemented
and tested; independent semantic acceptance remains open.
