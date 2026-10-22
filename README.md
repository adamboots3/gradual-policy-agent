# GitHub Policy Support Agent

A take-home assignment: a conversational assistant grounded in a pinned snapshot of
[GitHub's policy repository](https://github.com/github/site-policy).

**Current status:** a LangChain/LangGraph conversational backend with keyword or
hybrid retrieval, durable conversations, bounded search and validated citation IDs.
An interactive CLI, JSON API, React web UI and source-anchored evaluation suite are
implemented. The final configuration uses DeepSeek chat and Alibaba embeddings.
55 backend tests and 6 frontend tests passed; a real 45-scenario / 51-turn run
completed with valid citation provenance in every turn. Response-kind agreement was
49/51, which is **not answer accuracy**. Known semantic failures and the retrieval
comparison are documented in [Results](docs/RESULTS.md). Docker and remote CI remain
unverified; the source is prepared for a GitHub handoff.

## Run locally

Requirements: Python 3.12, Git, and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Run all commands from the repository root. Windows, macOS and Linux use the same
`uv run` commands; virtual-environment activation is unnecessary.

```sh
uv sync --locked
uv run policy-agent sync
uv run policy-agent index
uv run policy-agent search "How can I appeal an account suspension?"
uv run uvicorn policy_agent.api:app --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000/docs> for the API explorer. `GET /api/health` checks the
server; `GET /api/knowledge` reports the indexed snapshot;
`POST /api/knowledge/search` accepts `{"query":"appeal reinstatement","limit":6}`.
Before indexing, search returns HTTP 503 with setup instructions.

For the web interface, install Node.js 24 and open a second terminal:

```sh
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to the backend on port 8000; no
browser-side credentials or CORS setup are needed. The UI shows model/corpus setup
issues explicitly. Choose a suggested question, submit a message, switch conversations
or select an inline citation to inspect original policy text. Only successful turns
are saved; failed questions remain editable. After a network interruption, reopen
the conversation before resending because the server may have completed the turn.

UI verification: `npm test`, `npm run format:check`, and `npm run build` from
`frontend/`. Scripts invoke Node directly so Windows directories containing spaces
or `&` work without relying on problematic command shims. No CDN fonts or runtime
asset downloads are required. See [UI notes](docs/UI.md).

The sync command downloads the public corpus and checks out the commit recorded in
`corpus.lock.json`. Indexing can run without network access after sync. Sync refuses
to overwrite a dirty checkout. The generated SQLite database and downloaded source
are excluded from Git. Do not change the corpus lock without rerunning evaluations.

## Verify without API keys

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m evals.answers --validate
uv run python -m evals.retrieval --output evals/reports/retrieval.json
```

Tests use temporary synthetic documents, scripted chat responses and deterministic
embedding doubles to check plumbing and control flow. They make no network/model
calls. The retrieval evaluation uses the real indexed corpus, so run sync/index
first. It measures expected-document Recall@6, not factual answer accuracy.
The initial dataset is small and is a baseline, not a comprehensive eval suite.
The recorded [baseline report](evals/reports/retrieval-baseline.json) covers 12 English
questions: every expected document appears among the first six retrieved chunks.
This is document coverage within chunk results, not section-level evidence accuracy.

The [answer eval suite](evals/README.md) contains 45 source-anchored scenarios and 51
turns. `--validate` checks cases and source excerpts without paid calls. After model
setup, use `uv run python -m evals.answers --live --limit 3` for a paid smoke run,
then omit `--limit` for all scenarios. Reports separate structural checks from
human-reviewed correctness, grounding and citation support. The committed
[final live report](evals/reports/answers-hybrid-final.json) contains actual responses,
citations and traces. [Agent review notes](evals/REVIEW.md) identify remaining
failures; human review fields remain unfilled. The set is public development data.

## Model configuration

Copy `.env.example` to `.env` using your OS file-copy command. No secret is required
for corpus indexing, keyword search or tests. Real conversations require a provider
key and a chat model supporting tool calling. Provider and model selection are not
predefined. The lazy factories use LangChain's `init_chat_model` and `init_embeddings`.

Install provider adapters with `uv sync --locked --all-extras` (or just
`--extra compatible` / `--extra anthropic`). The compatible extra installs
`langchain-openai`; the Anthropic extra installs `langchain-anthropic` for chat.
Other providers require adding and locking their own LangChain integration.

Set `POLICY_CHAT_PROVIDER` to the LangChain provider identifier, `POLICY_CHAT_MODEL`
to a tool-capable model you have access to, and `POLICY_CHAT_API_KEY` to its key.
For a compatible endpoint, use provider identifier `openai` and configure
`POLICY_CHAT_BASE_URL` to that endpoint's API base URL. The endpoint must support
function/tool calling; a text-only completion endpoint is insufficient.
Anthropic chat uses provider identifier `anthropic`. Endpoint/model compatibility
still requires a real smoke test once your provider has been selected.

For DeepSeek's official compatible endpoint, the tested configuration is:

```dotenv
POLICY_CHAT_PROVIDER=openai
POLICY_CHAT_MODEL=deepseek-flash
POLICY_CHAT_BASE_URL=https://api.deepseek.com
POLICY_CHAT_API_KEY=YOUR_DEEPSEEK_KEY
POLICY_CHAT_EXTRA_BODY={"thinking":{"type":"disabled"}}
POLICY_RETRIEVAL_MODE=keyword
```

Here `openai` selects LangChain's compatible client; requests go to the configured
DeepSeek endpoint. Non-thinking mode avoids relying on vendor-specific reasoning
history handling during tool calls. See [DeepSeek setup](https://api-docs.deepseek.com/zh-cn/)
and [thinking-mode guidance](https://api-docs.deepseek.com/guides/thinking_mode/).
The complete live evaluation and a Chinese two-turn browser demonstration used
this endpoint; see [actual demo](docs/DEMO.md) and [results](docs/RESULTS.md).

```sh
uv run policy-agent chat
# To resume a printed conversation ID:
uv run policy-agent chat --conversation YOUR_CONVERSATION_ID
```

Type `/exit` to quit. CLI responses print numbered citation links. The API offers
conversation create/list/get/delete endpoints and a message endpoint documented in
`/docs`. Missing configuration returns HTTP 503; upstream failures return a sanitized
502. Failed turns are not inserted into the user-facing dialogue history.

For hybrid retrieval, configure the independent `POLICY_EMBEDDING_*` settings, then:

The tested Alibaba Bailian configuration uses the **Beijing** region. Keep this key
separate from the DeepSeek chat key:

```dotenv
POLICY_EMBEDDING_PROVIDER=openai
POLICY_EMBEDDING_MODEL=qwen3.7-text-embedding-flash
POLICY_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
POLICY_EMBEDDING_API_KEY=YOUR_BEIJING_BAILIAN_KEY
POLICY_EMBEDDING_BATCH_SIZE=20
```

The compatible adapter sends raw text and requests float vectors. All 721 chunks
were embedded successfully with 1,024 dimensions. Other regions/models may require
a different URL or batch limit; configure the endpoint matching your own key.

```sh
uv run policy-agent embed
```

Set `POLICY_RETRIEVAL_MODE=hybrid` in `.env` after the embedding build succeeds.
This command sends the policy text to the embedding provider and can incur charges.
It batches requests and reuses a matching existing cache. Changing provider, model
or base URL requires rebuilding. Re-indexing policies invalidates the vector cache.
Hybrid mode fails explicitly if the index is missing or incompatible; it does not
silently fall back to keyword search. Keyword mode remains an English baseline;
the agent is prompted to formulate English search queries for it.

Never commit `.env`, API keys or private conversation data. Conversations, run
traces and graph checkpoints are stored under `data/` and excluded from Git.

## Docker (full stack)

```sh
docker compose up --build
docker compose run --rm backend uv run --no-sync policy-agent sync
docker compose run --rm backend uv run --no-sync policy-agent index
# If .env enables hybrid retrieval:
docker compose run --rm backend uv run --no-sync policy-agent embed
docker compose run --rm backend uv run --no-sync python -m evals.answers --validate
```

The web interface is available at <http://localhost:8080>; the API explorer remains
available at <http://localhost:8000/docs>. Nginx forwards `/api` to the backend.
Corpus, index, conversations and checkpoints persist in a
named volume. Both optional provider integrations are installed in the image;
Compose reads `.env` at runtime if present (Compose 2.24+). No credentials are
embedded in the image. Docker is an alternative
to the native steps; its runtime validation is pending because Docker is unavailable
on the current development machine. The frontend image installs from its npm lockfile.
GitHub Actions is configured to build/start both containers and check the frontend
and proxied health endpoint, but that workflow has not yet run in a remote repository.

Run one API worker: per-conversation serialization currently uses process-local locks.
Stop the server before replacing the corpus. Chat keeps the last six completed turns
by default (`POLICY_HISTORY_TURNS`); older turns remain visible in stored history but
are not sent to the model. The local application has no authentication.

Citation validation checks provenance and syntax, not whether every claim is actually
supported. Non-policy response kinds (greeting, clarification, out-of-scope and
insufficient-evidence) are model classifications; semantic misuse of those kinds and
prompt-injection resistance must be assessed in live answer evaluations.

## Project notes

- [Implementation plan](docs/PLAN.md): scope, milestones, acceptance checks and status.
- [Architecture and contracts](docs/ARCHITECTURE.md): state, API and evidence design.
- [Verification record](docs/VERIFICATION.md): executed checks and remaining limitations.
- [Results and limitations](docs/RESULTS.md): real runs, retrieval comparison and known failures.
- [Live demonstration](docs/DEMO.md): Chinese follow-up with source links and screenshots.
- [Submission checklist](docs/ACCEPTANCE.md): local handoff and remaining GitHub/CI steps.
- `.github/workflows/ci.yml`: Windows/Linux installs, backend and frontend tests,
  production build, and Linux container smoke checks.

The repository snapshot is the assignment's evidence source. It may differ from
GitHub's live policy documentation. Relative links and Liquid template expressions
inside the original Markdown are preserved rather than represented as rendered
documentation. Citations link to the exact repository version and original lines.
