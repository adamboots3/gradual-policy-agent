# Current verification record

Reviewed on 2026-10-24 (Asia/Shanghai), against the online-reading architecture.
This record describes the maintained project tree and executed checks. Previous
implementation experiments and their logs remain recoverable in Git history.

## File audit

The audit covered all 65 maintained files: backend modules, frontend source/styles/build scripts, tests,
evaluation code/dataset/report, diagrams, screenshots, Markdown, dependency locks,
environment examples, ignore rules, Docker/Compose and CI configuration.
Generated environments, installed dependencies, local credentials and development
caches are not distributed project source and were not published.

- Removed obsolete keyword/hybrid datasets, reports, review notes and screenshots.
- Replaced chronological milestone notes with current scope, runtime behavior,
  current validation and explicit limitations. Removed references to deleted files.
- Retained `evals/reports/answers-online.json` unchanged. New live evaluations write
  `answers-local.json` by default, keeping the recorded baseline intact.
- Removed the old health-stage label, unused history-loading CSS, the empty
  chunk-heading field and the unused 204-response branch in the frontend client.
- Source panels now show actual file paths and clear previous evidence when a
  new response has no citations.
- Invalid GitHub response shapes, commit/tree metadata and file sizes produce
  sanitized source failures; unknown chat request fields are rejected.
- Corrected evaluation help: dataset validation reads GitHub but does not call
  the model. Dependency manifests and locks were checked without upgrading packages.
- Checked project wording, UTF-8 source, Python syntax, JSON/TOML structure, local
  Markdown links, diagram consistency and references to removed modules.

## Executed engineering checks

| Check | Result |
| --- | --- |
| Backend regression | **79 passed in 2.44s**; mocked GitHub/model responses, no paid calls |
| Python lint/format | Ruff checks and formatting passed |
| Frontend regression | **14 passed** with Vitest/React Testing Library |
| Frontend build | TypeScript checking and Vite production build passed |
| Dataset/source validation | **45 scenarios / 51 turns / 36 anchors** checked online; no model calls |
| Recorded-report recheck | All **51 turns** independently rechecked against GitHub; recorded checks and coverage match |
| Lock/manifest consistency | Python lock parsed; npm root dependencies/version match the manifest |

Backend coverage includes state isolation, all 20 supplied historical pairs,
oldest-first trimming, overflow retries, tool-call/result integrity, citation
repair, request-only caching, immutable versions, source bounds, malformed source
metadata and sanitized errors. Negative checks keep removed routes and persisted
chat behavior from reappearing.

Frontend coverage includes citations from distinct passages of one read, source
paths, follow-ups, independent windows, remount/reset/page-exit behavior, failure
retry, duplicate prevention and clearing stale source details on uncited replies.

The Windows sandbox stalled the in-process HTTP test client. The full deterministic
backend run passed outside that sandbox; this was an execution-environment constraint.
It did not require changes to the application or model credentials.

## Real browser verification

Used temporary ports 8001/5174, leaving existing services untouched. At the browser's
normal 1280×720 viewport, a Chinese appeal-deadline question and the contextual
follow-up about submission both completed with original-line citations. The source
panel displayed the file path and immutable GitHub link without horizontal overflow.
The current captures are linked in [DEMO](DEMO.md). A fresh-window greeting used
zero file reads and no citations; new-chat reset and a separate empty tab were
verified. The transition from an existing source to an uncited response is covered
by the component regression. In one manual turn after policy discussion, the model
treated a greeting as a continuation of the prior question; this is a remaining
context-following issue rather than a source-panel failure.

These are real API responses, not UI fixtures. They verify the interaction, not
every policy interpretation; the model still tends to add unnecessary overviews.

## Evaluation evidence and remaining limits

The recorded `policy-agent-online-v2` run completed 51/51 turns without request
errors: 50/51 expected kinds, 51/51 provenance checks, 94.4% expected-document
coverage and 92.2% anchor coverage. Its timestamp, model, source commit and raw
responses remain unchanged. This maintenance pass does not claim a new semantic
score. Known findings and unreviewed human fields are described in
[ONLINE_RESULTS](ONLINE_RESULTS.md).

There is no independent semantic accuracy score, load benchmark or reconciled
provider cost. Authentication and public deployment are outside the current scope.
Docker is unavailable on this local host; container build/start/health and fresh
Windows/Linux installs are checked by the repository workflow. CI results apply
only to their associated commit; use [Actions](https://github.com/adamboots3/gradual-policy-agent/actions/workflows/ci.yml)
to verify the published revision. Container health checks do not exercise paid model calls.
