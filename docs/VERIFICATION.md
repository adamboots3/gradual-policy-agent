# Verification record

This is a chronological development log. Earlier pending statuses are superseded by
the final acceptance entry below and `RESULTS.md`.

## Native verification — 2026-10-22 (Asia/Shanghai)

Environment: Windows, Python 3.12.7, uv 0.13.5. Dependencies were resolved against
the public PyPI registry, captured in `uv.lock`, installed with `uv sync --locked`,
and checked again with `uv sync --locked --offline` using the populated cache.

Executed successfully:

- `ruff check .`: all checks passed.
- `ruff format --check .`: 16 files already formatted.
- `pytest -q --tb=short --basetemp data/pytest-run-02`: **17 passed**.
- Corpus indexing: **57 Markdown documents, 721 chunks**, parser version 1.
- An independent comparison of every stored chunk with its source line range:
  **721 of 721 matched exactly**.
- Keyword retrieval baseline: **12/12 questions** had their expected policy document
  among the first six chunks (mean expected-document Recall@6 = 1.0).
  Dataset/report: `evals/datasets/retrieval.jsonl` and
  `evals/reports/retrieval-baseline.json`.

Corpus commit: `b9578b546d2506febda1da2cd7431644d58e512c`.

The Windows sandbox initially prevented pytest temporary-directory creation and
then stalled the in-process HTTP client. Tests passed outside that sandbox with a
workspace-local temporary directory. These are host execution constraints, not
changes to application behavior. Package downloads and source cloning also required
normal network access outside the sandbox.

## Agent-backend verification — 2026-10-22 (Asia/Shanghai)

Implemented hybrid retrieval, lazy provider factories, bounded LangGraph tool calling,
durable conversations, citation validation, conversation APIs and interactive CLI.

- `pytest -q --tb=short --basetemp data/pytest-agent-03`: **46 passed**.
- `ruff check .`: all checks passed.
- `ruff format --check .`: 26 files already formatted.
- Initialized `ChatOpenAI`, `OpenAIEmbeddings` and `ChatAnthropic` adapters using dummy
  model/key values, without invoking them. This verifies installed package interfaces,
  not endpoint connectivity, model availability or authentication.
- Repeated the real-corpus keyword baseline: **12/12**, unchanged. Report generated
  locally at `evals/reports/retrieval-after-agent.json` (ignored, reproducible command).

New deterministic tests cover embedding batching/cache reuse, invalid vectors,
model/dimension mismatch, index invalidation, persisted follow-up history, stale and
fabricated citations, search limits, failure/retry behavior, conversation isolation,
same-conversation concurrency, checkpoint deletion, API contracts and sanitized errors.
These tests execute the actual graph and database code against scripted chat/embedding
doubles. A synthetic Chinese query only tests vector-routing plumbing; it does not
establish Chinese language retrieval quality.

The optional adapter packages were installed from the existing lock with
`uv sync --locked --all-extras`. No credentials were provided or model calls made.

## Web UI and evaluation-suite verification — 2026-10-22 (Asia/Shanghai)

- Backend regression: `pytest -q --tb=short --basetemp data/pytest-ui-eval-02`:
  **51 passed**.
- Frontend: a fresh `npm ci --no-audit --no-fund` completed from `package-lock.json`.
  **6 component tests passed**; `npm run format:check` and `npm run build` passed.
  The production build includes strict TypeScript checking.
- Backend lint and formatting: all checks passed, 30 Python files formatted.
- `python -m evals.answers --validate`: **45 scenarios, 51 turns, 36 source anchors**
  validated against the clean pinned policy checkout, without model calls.
- Local frontend and proxied backend health both returned HTTP 200.
- Browser QA at a 614px-wide viewport verified initial model/corpus status, suggested
  input, the actual HTTP 503 missing-provider flow, and preservation of the failed
  question. Corrected a flex minimum-height issue discovered in that check. The
  screenshot is in `docs/screenshots/policy-desk.jpg`; no fake answer is shown.
- Removed the single empty conversation created by browser QA and stopped the
  development servers after verification.

The component tests mock API responses; backend graph tests use scripted models.
Neither provides live-model quality results. Desktop-size browser layout and live
answer rendering were not visually verified in this viewport.

Prepared full-stack Compose, frontend Nginx proxy and health checks, and CI jobs for
Windows/Linux frontend checks plus a Linux Docker smoke test. These container/remote
CI checks remain unexecuted on this machine. No live answer report has been generated.

## Gaps at the pre-provider milestone (historical)

- Docker build and runtime; Docker is unavailable on this host.
- GitHub Actions execution; the workflow is prepared but this is not a published repo.
- Clean installation on a second OS or a fresh container.
- Real semantic/cross-language retrieval quality and comprehensive live-agent coverage.
- Answer correctness, grounding, citation support, multi-turn behavior and cost.

The small keyword baseline includes obvious policy terminology and only checks
document retrieval. It does not demonstrate that the specific supporting clauses
were retrieved, that ambiguous questions were understood, or that answers are correct.

Chat is now configured with DeepSeek (see the smoke test below). Embedding selection,
comprehensive live evaluation and container runtime verification remain pending.

## DeepSeek configuration smoke test — 2026-10-22 (Asia/Shanghai)

The user configured their API key locally. Non-secret configuration uses the official
DeepSeek endpoint, model `deepseek-flash`, compatible provider identifier `openai`,
and `extra_body={"thinking":{"type":"disabled"}}`. Keys were neither printed nor
copied into source, reports or command arguments.

A single real English policy question about the appeal deadline completed in 5,126ms:
one search, two model calls, and three versioned citations. The six-month deadline
and the cited source passages were consistent with the pinned policy. The temporary
smoke-test conversation was removed. This is a connection/tool/citation smoke check,
not a completed quality evaluation or measured multi-turn/cross-language result.

Deterministic tests now override project settings with clean defaults so a local
`.env` containing credentials cannot cause an unintended live-provider call.


## Final local acceptance — 2026-10-22/23 (Asia/Shanghai)

- Configured the user's independent DeepSeek and Beijing Bailian keys locally;
  never printed credentials. The embedding smoke test returned 1,024 dimensions,
  then the entire 721-chunk embedding build completed with batch size 20.
- Extended fixed-set retrieval: keyword 16/24; hybrid 22/24. English subsets both
  16/18; Chinese keyword 0/6 and hybrid 6/6. Raw comparison reports are committed.
- Three full live answer runs each completed 45 cases / 51 turns without request
  errors. Final hybrid kind agreement: 49/51; citation provenance and corpus version:
  51/51. See `RESULTS.md`; structural success is not semantic correctness.
- Inspected all final answers for core expected facts, preserving semantic issues
  in `evals/REVIEW.md`. Independent human review and monetary-cost reconciliation
  are still outstanding. No human semantic score is claimed.
- Fixed observed retrieval-context/refusal problems; added regression coverage.
  Final backend regression passed 55 tests in the original environment.
- Copied source without ignored credentials/artifacts into a separate review folder,
  performed locked installation in a new environment, and ran its then-current 52
  tests. Subsequently built the final wheel, reinstalled it into that separate
  environment, verified imports from `site-packages`, and ran all final 55 tests:
  **55 passed in 18.95s**. This is Windows clean-environment/wheel verification,
  not another-OS or container verification.
- The frontend's clean install, six tests, formatting and production build remain
  the latest UI checks; no frontend source changes followed them.
- Real browser flow: Chinese appeal deadline, contextual follow-up asking where to
  submit, source 1/source 2 inspection, reload and reopening the saved history.
  Verified original excerpts and immutable line links, including Community Guidelines
  lines 66–68. Captures: `live-citation.jpg` and `live-followup.jpg`; transcript:
  `DEMO.md`. Only a 614px viewport was visually inspected.
- Removed only the known two-turn QA conversation after exporting its transcript;
  stopped the two development servers started for acceptance.
- Initialized the local Git repository on `codex/policy-support-agent`; selected
  sanitized source/reports for handoff. The user's GitHub repository does not yet
  exist, so no push or remote CI execution has occurred.

Still unverified: Docker build/runtime, other operating systems, remote GitHub CI,
independent human answer adjudication, load behavior and exact provider cost.


## GitHub delivery and CI — 2026-10-23 (Asia/Shanghai)

At the user's request, inspected the other assignment's private `adamboots3/gradual-chat`
repository and reused the existing authenticated account. Created the private
[adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent)
repository and uploaded source revision `b8af71c` to default branch `main`.
The local `codex/policy-support-agent` branch tracks `origin/main`.

[Verification run](https://github.com/adamboots3/gradual-policy-agent/actions/runs/39810856851) completed successfully:

- Backend on Ubuntu and Windows: locked dependency install, Ruff checks and pytest.
- Frontend on Ubuntu and Windows: locked npm install, tests, formatting and build.
- Containers on Ubuntu: Compose build, healthy startup of both services, frontend
  HTTP response, proxied API health response and cleanup.

All five jobs passed. No model keys were uploaded or configured in Actions. Container
corpus sync/index and live model calls are outside this smoke check's coverage.
Source behavior was unchanged after this verified revision; the following handoff
commit updates only documentation. Earlier statements that remote CI or repository
creation remained pending are historical and superseded by this entry.


## Window-only context and web-only access — 2026-10-24 (Asia/Shanghai)

User-requested scope change: remove persisted conversations and CLI chat. Completed
pairs live only in React page memory and travel with each `/api/chat` request. New
windows, refresh, page exit and new-chat discard that state. The server builds a
fresh graph per request, without checkpointing, conversation tables or run records.
Former conversation CRUD/resume routes and CLI console entry were removed. Policy
initialization remains `python -m policy_agent.setup`; policy/vector data is retained.

Executed checks:

- Created a separate environment from the updated lock with all optional adapters;
  confirmed `langgraph.checkpoint.sqlite` is absent and no `policy-agent` console
  entry exists. Removed three obsolete packages from the lock; remaining versions
  were not upgraded.
- Final backend suite: **63 tests passed in 15.44s** in the clean environment,
  including all six evaluation regressions. Tests cover
  explicit bounded context, independent concurrent requests, failed-turn cleanup,
  no chat files, removed routes, no-store responses and missing configuration.
- Frontend: 11 tests passed; TypeScript/production build and formatting passed.
  Covered in-window follow-ups, two independent windows, remount reset, new chat,
  page exit and late reply suppression, no browser storage writes, failure retry,
  duplicate prevention, citation rendering and API context serialization/bounds.
- Dataset validation: 45 scenarios / 51 turns / 36 anchors passed, without paid calls.
- Real browser at 1280×720: Chinese appeal deadline answered with six months and a
  real source; follow-up “那应该在哪里提交？” resolved to the appeal form. A new tab,
  refresh, and closing/reopening all showed an empty chat. Captures are
  `window-memory-chat.jpg` and `window-memory-empty.jpg`.
- Used temporary ports 8001/5174 because other existing processes occupied 8000/5173.
  Stopped only the temporary acceptance servers. Existing processes were not stopped;
  they need restarting before they can serve the revised source.
- Legacy conversation/checkpoint files in local data were verified empty. An old
  running process held a file lock, so they were left untouched; the new implementation
  never reads or writes them. Fresh environments create no such files.

The complete historical answer-quality suite was not rerun for this transport/state
change. Its failures remain open; the two-turn smoke check is not a replacement
quality score. The previous remote CI run applies to the baseline revision, not this
new local update. No model keys were changed or published.

## Frontend-owned 20-turn context and oldest-first trimming — 2026-10-24

Supersedes the fixed six-turn selection in the preceding revision. Each request
starts from all of its supplied completed pairs (up to 20). Before every model
call, including after search, the agent budgets system text, tool schemas, history,
the current question and current-turn messages, with output/margin reservations.
It removes oldest complete historical pairs; current question and tool-call/result
relationships remain intact. Recognized provider overflow responses trigger bounded
further trimming. No history summary or persistence was added. The page's display
history is not changed by backend trimming.

Executed checks:

- Backend: **76 tests passed in 16.81s**; Ruff lint and formatting passed. Covered
  all 20 supplied turns (including ignoring obsolete `POLICY_HISTORY_TURNS=6`),
  schema/output/multilingual budgeting, exact fit boundaries, oldest whole-pair
  removal after retrieval, provider-overflow retries, retry exhaustion, unrelated
  error propagation, no-history-left 422 responses, and a fresh request after
  trimming. Existing isolation, no-persistence, retrieval and citation regressions
  remain passing.
- One live follow-up using 20 synthetic completed pairs: `answered`, all 20 pairs
  retained, zero trimmed, two successful model calls, two searches, one citation;
  request latency 8,425ms. This verifies transport/context integration and the
  configurable output limit; it is not a complete answer-quality evaluation.
  Dialogue and traces were not saved.
- Local compatible-endpoint configuration now explicitly supplies the selected
  model's 1,000,000-token context capacity, based on the provider's published
  [model limits](https://api-docs.deepseek.com/quick_start/pricing/). Credentials
  were not changed; `.env` remains Git-ignored. Shared code and example config
  remain provider-independent. Unknown models use an explicit documented fallback,
  not an assertion that every model has the same window.
- Frontend source and dependency locks were unchanged, so frontend checks were not
  repeated for this backend-only change. The historical live quality suite was
  not rerun; its documented limitations remain open.

Token counts use LangChain's local approximation with a non-ASCII allowance,
not an exact provider tokenizer. Conservative estimates may trim earlier than
strictly necessary; recognized provider overflow retries handle underestimates.
If current-turn material alone cannot fit, the API returns an actionable 422.
`model_calls` counts successful responses; overflow rejections are separate trim
events in explicit evaluation traces, bounded by at most 20 removed pairs.

The preceding web-only commit `4bc4639` passed all five jobs in
[GitHub Actions](https://github.com/adamboots3/gradual-policy-agent/actions/runs/39989034601).
This context-budget revision has been verified locally and has not yet been pushed.
