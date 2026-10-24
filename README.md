# GitHub Policy Support Agent

[English](README.md) | [简体中文](README.zh-CN.md)

A web assistant built with LangChain, LangGraph, FastAPI and React/TypeScript.
It browses [github/site-policy](https://github.com/github/site-policy) online:
list policy files, let the LLM choose files, read their original lines, then answer
with verified source excerpts. No local policy database, keyword/vector index,
embedding service, document ingestion or prebuilt chunks are required.

Repository: [adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent)
(public). Further documentation: [verification](docs/VERIFICATION.md), [current results](docs/ONLINE_RESULTS.md),
[evaluation](evals/README.md).

## Implemented capabilities

| Capability | Status |
| --- | --- |
| Multi-turn conversations with temporary history | ✅ |
| Source citations with original excerpts and versioned links | ✅ |
| Web UI for interacting with the agent | ✅ |
| Repeatable evaluation suite with 45 scenarios / 51 turns | ✅ |

> **Start with the design diagrams:**
>
> - [System sequence diagram](docs/ARCHITECTURE.md): follow a question through the web client, Agent, LLM and GitHub reading tools.
> - [Agent structure and execution](docs/AGENT_INTERNALS.md): explore LangChain/LangGraph, state, tool calling, validation hooks and routing.

**Demo (Chinese, about 63 seconds):** [Open / download the walkthrough video (MP4)](https://github.com/adamboots3/gradual-policy-agent/releases/download/demo-video/policy-agent-demo.mp4).
The walkthrough shows a policy question, source citations, opening the original policy on GitHub, and a follow-up question. Chinese subtitles are included as an optional track.

## Run locally

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/),
Node.js 24, and network access to GitHub and your chosen model API.

```sh
git clone https://github.com/adamboots3/gradual-policy-agent.git
cd gradual-policy-agent
uv sync --locked --all-extras
```

Copy `.env.example` to `.env`. Select a model with tool calling. For a compatible
endpoint, use LangChain's `openai` adapter with your own model and base URL:

```dotenv
POLICY_CHAT_PROVIDER=openai
POLICY_CHAT_MODEL=YOUR_TOOL_CAPABLE_MODEL
POLICY_CHAT_BASE_URL=YOUR_COMPATIBLE_API_BASE_URL
POLICY_CHAT_API_KEY=YOUR_CHAT_KEY
POLICY_CHAT_CONTEXT_WINDOW_TOKENS=YOUR_MODEL_CONTEXT_CAPACITY
```

`openai` selects an adapter, not a fixed model vendor. The `anthropic` adapter is
also locked; additional providers need their own integration. The optional
`POLICY_CHAT_EXTRA_BODY` accepts provider-specific JSON. Only the backend reads
credentials. No Embedding API key or policy initialization command is needed.
Model generation may incur your provider's charges.

`POLICY_GITHUB_REF=HEAD` follows the policy repository's default branch. Every
question resolves it once, then reads and cites one immutable commit. Set a full
commit SHA to use a specific version. GitHub access to this public repository works
without a token; optionally set `POLICY_GITHUB_TOKEN` for higher REST API limits.
Use a token with read access only. Model keys and GitHub tokens are independent.
GitHub rate limits or network failures produce an explicit error rather than a
policy answer reconstructed from model memory.

```sh
uv run uvicorn policy_agent.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

Open [the web client](http://localhost:5173); [API explorer](http://localhost:8000/docs).
Vite proxies `/api` to port 8000. To change the development backend, set
`POLICY_API_PROXY_TARGET` before starting Vite. Restart existing processes after
updating the source. The web client is the only conversation interface.

## Agent and citations

The model has three tools:

| Tool | Purpose |
| --- | --- |
| `list_policy_documents()` | Get policy file paths and sizes, fixing this turn's commit |
| `read_policy_document(path, start_line, line_count)` | Open a selected file and return numbered original lines |
| `submit_answer(kind, answer, citations)` | Submit an answer with exact original-line references |

The LLM chooses files by directory and filename; it can open more files or continue
a long document. There is no algorithmic relevance ranking or automatic chunk
selection. Defaults allow six read attempts, two directory requests and ten
successful model responses per question, with at most four tools per response.
Each read returns at most 200 lines and 24,000 characters, plus continuation metadata.
The server checks Git blob identity; repeated reads within one question reuse an
in-memory file. No policy contents or conversation state are written to disk.

For policy answers the model supplies `[[1]]`, `[[2]]` markers and cited line ranges.
Each numbered list entry binds a source ID to an exact range; different passages
from the same read can have separate citation numbers.
The server checks that each reference selects 1–80 lines actually read in this
question, extracts the original text and creates an immutable GitHub URL. This
checks provenance, **not whether every claim is semantically supported**. File
selection, missed conditions and unsupported interpretations remain model risks.

## Temporary context and API

Completed turns live only in the current page's React memory. Refresh, navigation,
closure or New conversation discards them. There is no saved-history UI, browser
storage, server conversation database or persistent graph checkpointer.

```json
{
  "content": "Where should I submit it?",
  "history": [{"question": "Can I appeal a suspension?", "answer": "Previous response"}]
}
```

`POST /api/chat` accepts at most 20 completed question/answer pairs, each bounded
at 4,000/6,000 characters. It uses all supplied pairs when they fit. Before every
model call, including after online reads, it budgets system text, tool schemas,
history, current question and current-turn messages. It reserves output capacity
and removes the oldest **complete historical pair** until estimated input fits.
The current question and current-turn tool call/result pairs remain intact.
Recognized provider context errors trigger further bounded trimming and retry.
No summaries or previous-turn agent/tool execution are imported.

`POLICY_CHAT_CONTEXT_WINDOW_TOKENS=0` uses the LangChain profile when available,
otherwise a documented 32,768-token fallback. Custom endpoints should set their
actual capacity explicitly. Output is capped at `POLICY_CHAT_MAX_OUTPUT_TOKENS`
(default 2,048), with `POLICY_CHAT_CONTEXT_MARGIN_TOKENS` (default 512) reserved.
Token counts are conservative local estimates, not an exact vendor tokenizer.
If mandatory current-turn material alone cannot fit, the API returns a clear 422.
Trimming affects LLM input, not the page's displayed history.

| Endpoint | Contract |
| --- | --- |
| `GET /api/health` | Backend/model configuration status, without external calls |
| `GET /api/policies` | Repository/ref configuration, without spending GitHub API quota |
| `POST /api/chat` | One question plus temporary history; returns answer and source excerpts |

Responses include `source_commit`, `read_calls`, model/prompt metadata, latency and
received/used/trimmed history counts. Greetings can have a null source commit when
no policy was read. Chat responses use `Cache-Control: no-store`. Source/configuration
failures return 503, context/schema failures 422, other provider failures a sanitized
502. Unknown request fields are rejected. No authentication or public application
deployment is included.

## Verify and evaluate

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m evals.answers --validate
```

Tests use scripted models and mocked GitHub responses; they need no model keys or
network. Dataset validation reads the pinned reference files online but makes no
model calls. From `frontend/`: `npm test`, `npm run format:check`, `npm run build`.
The [evaluation suite](evals/README.md) covers 45 scenarios / 51 turns with exact
source anchors. Live evaluation uses the same online agent and incurs model costs.
The [final online run](docs/ONLINE_RESULTS.md) completed 51/51 turns with no request
errors, 50/51 expected-kind agreement and 51/51 provenance checks. These are not
semantic accuracy scores; file-selection and interpretation failures remain.
New live runs write a separate ignored report; the recorded report is not overwritten
by default. See [verification](docs/VERIFICATION.md) for current engineering checks.

## Containers

```sh
docker compose up --build -d --wait
```

Open [the containerized web client](http://localhost:8080). Compose reads `.env`
when present; missing model configuration is shown by the UI. No data volume,
Git clone, index construction or embedding step is needed. Health checks require
neither model keys nor GitHub access. Windows/Linux backend and frontend CI plus
Docker build/start/health checks are defined in `.github/workflows/ci.yml`.
