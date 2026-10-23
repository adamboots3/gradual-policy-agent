# GitHub Policy Support Agent

A web-based policy support assistant built with LangChain, LangGraph, FastAPI and
React/TypeScript, grounded in a pinned snapshot of [GitHub policies](https://github.com/github/site-policy).

Repository: [adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent)
(private; reviewers need access). See [results](docs/RESULTS.md) for real evaluation
reports and known answer-quality limitations.

## Temporary conversations, web access only

Chat context lives only in the current page's memory. Follow-ups in that window
carry completed question/answer pairs to the server. New tabs/windows start empty.
Closing, navigating away, refreshing, or choosing **New conversation** discards the
current chat. There is no history list, resume endpoint, browser storage, server
conversation database, or persistent graph checkpointer. Failed questions remain
editable in the current window and are excluded from follow-up context.

The only end-user interface is the web client. The former CLI chat and its console
entry point were removed. The initialization module below only prepares/inspects the
policy library; it is not a conversation interface. Policy documents, indexes and
embedding vectors remain on disk. The application does not save ordinary chat text
or tool traces. Explicit evaluation commands still write synthetic test reports.

## Native setup

Requirements: Python 3.12, Git, [uv](https://docs.astral.sh/uv/getting-started/installation/),
and Node.js 24. Run backend commands from the repository root.

```sh
git clone https://github.com/adamboots3/gradual-policy-agent.git
cd gradual-policy-agent
uv sync --locked --all-extras
uv run python -m policy_agent.setup sync
uv run python -m policy_agent.setup index
uv run python -m policy_agent.setup status
```

Copy `.env.example` to `.env` using your OS file-copy command. Choose a chat model
with tool calling; configure provider, model, endpoint and key independently of
embeddings. Missing configuration is shown explicitly, not replaced by fake answers.

```dotenv
POLICY_CHAT_PROVIDER=openai
POLICY_CHAT_MODEL=YOUR_TOOL_CAPABLE_MODEL
POLICY_CHAT_BASE_URL=YOUR_COMPATIBLE_API_BASE_URL
POLICY_CHAT_API_KEY=YOUR_CHAT_KEY
POLICY_RETRIEVAL_MODE=keyword
```

Here `openai` selects LangChain's compatible client, not a fixed model vendor.
Anthropic chat uses `anthropic`; other integrations require their own locked adapter.
The optional `POLICY_CHAT_EXTRA_BODY` passes provider-specific options. Model keys
stay on the backend and must never be committed.

For hybrid retrieval, configure independent `POLICY_EMBEDDING_PROVIDER`,
`POLICY_EMBEDDING_MODEL`, `POLICY_EMBEDDING_BASE_URL`, `POLICY_EMBEDDING_API_KEY` and
`POLICY_EMBEDDING_BATCH_SIZE`. Then run:

```sh
uv run python -m policy_agent.setup embed
```

This sends policy text to the selected embedding service and may incur charges.
After a successful build, set `POLICY_RETRIEVAL_MODE=hybrid`. Changing embedding
provider, endpoint or model requires a rebuild; re-indexing invalidates vectors.
Hybrid setup errors fail explicitly instead of silently falling back to keywords.

Start the backend:

```sh
uv run uvicorn policy_agent.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

Open [the web client](http://localhost:5173). Vite proxies `/api` to port 8000.
For an alternate development backend, set `POLICY_API_PROXY_TARGET` before starting
Vite; it is a server-side proxy setting, not a browser credential. Restart existing
backend/frontend processes after updating from the former persistent-history version.

The corpus is fixed by `corpus.lock.json` (57 documents / 721 chunks). Sync rejects
a dirty or mismatched checkout. Source citations use immutable commit URLs and exact
line ranges; the pinned source can differ from GitHub's currently published policy.

## API and context contract

[API explorer](http://localhost:8000/docs). `GET /api/health` and `/api/knowledge`
report configuration/corpus status. `POST /api/knowledge/search` searches policy
text. `POST /api/chat` handles a request with optional window-owned context:

```json
{
  "content": "Where should I submit it?",
  "history": [{"question": "Can I appeal a suspension?", "answer": "Previous completed response"}]
}
```

No conversation ID or cookie is required. At most 20 bounded completed pairs are
accepted; the model receives the last six by default (`POLICY_HISTORY_TURNS`).
Context is untrusted and is used to interpret follow-ups; policy claims still need
current-turn retrieval. The response includes answer, citations and diagnostic
metadata, without saved run records or ordinary tool traces. Chat responses use
`Cache-Control: no-store`. Configuration failures return 503; provider errors return
a sanitized 502. The application has no authentication. Stop chat requests before
replacing the corpus.

## Verify

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m evals.answers --validate
uv run python -m evals.retrieval --mode keyword
```

From `frontend/`: `npm test`, `npm run format:check`, `npm run build`. Deterministic
tests need no model keys. Source-based eval validation requires sync/index first.
Tests cover temporary context, isolation, failure handling, no conversation files,
retrieval and citation validation. Scripts invoke Node directly so Windows paths
containing spaces or `&` work.

For paid answer evaluation: `uv run python -m evals.answers --live`. Each scenario
keeps context in process memory only and resets it for the next case. Reports and
rubric: [eval suite](evals/README.md). Existing 2026-10-22 reports were run before the
window-memory change; they are historical quality evidence, not reruns of this revision.
Citation provenance checks do not prove that every claim is supported.

## Docker

```sh
docker compose up --build
docker compose run --rm backend uv run --no-sync python -m policy_agent.setup sync
docker compose run --rm backend uv run --no-sync python -m policy_agent.setup index
# If hybrid retrieval is configured:
docker compose run --rm backend uv run --no-sync python -m policy_agent.setup embed
```

Web: [localhost:8080](http://localhost:8080); API: port 8000. The named volume stores
only the policy library/index; conversations are not written there. Compose reads
`.env` at runtime (Compose 2.24+); keys are not embedded in images. Previous CI
passed Windows/Linux checks and Docker build/start/health for revision `b8af71c`;
current revision verification is recorded separately in [verification](docs/VERIFICATION.md).

## Documentation

- [Architecture and numbered sequence](docs/ARCHITECTURE.md)
- [Current scope and plan](docs/PLAN.md)
- [UI behavior](docs/UI.md)
- [Acceptance checklist](docs/ACCEPTANCE.md)
- [Historical live demo](docs/DEMO.md), [results](docs/RESULTS.md), [semantic review](evals/REVIEW.md)

Never commit `.env`, provider keys or private data. The specific providers used in
historical evaluations are recorded for reproducibility, not required defaults.
