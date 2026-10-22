# Architecture and contracts

## Data flow

```mermaid
flowchart LR
  A[Pinned Git policy snapshot] --> B[Markdown parser]
  B --> C[SQLite chunks and FTS5]
  B --> D[Embedding cache]
  U[React web client] --> API[FastAPI]
  API --> C
  API --> G[LangGraph conversation agent]
  G --> C
  G --> D
  G --> M[Configured chat model]
```

The backend graph, retrieval components and React client are implemented and tested
with scripted doubles and real DeepSeek/Bailian requests. See `RESULTS.md` for measured limits.

## Evidence contract (implemented)

Each chunk has `chunk_id`, `title`, `heading`, `content`, `path`, `start_line`,
`end_line`, `commit_sha`, `source_url`, and `content_hash`. IDs are deterministic
for one source version, file path, line range and content. URLs link to immutable
GitHub blob lines. YAML metadata is excluded without shifting body line numbers.
Markdown sections are split at headings, then at paragraph boundaries when large.
The size limit is soft so paragraphs, lists, tables and fenced code remain intact.

Index replacement is transactional, including the FTS index and corpus metadata.
Search tokenizes user input before constructing an FTS expression. FTS snippets
are evidence candidates, not a confidence estimate or proof of sufficient support.

## Implemented API

| Method | Path | Meaning |
| --- | --- | --- |
| GET | `/api/health` | Process health and implementation stage |
| GET | `/api/knowledge` | Snapshot SHA, document/chunk counts, parser version |
| POST | `/api/knowledge/search` | Keyword or hybrid results with immutable source metadata |

Search request: `{"query":"appeal a suspension","limit":6}`.
Search response: `{"retrieval_mode":"keyword","results":[...]}`.
An unindexed corpus returns 503. Invalid limits/empty query return 422.

## Implemented conversation API

| Method | Path | Meaning |
| --- | --- | --- |
| POST | `/api/conversations` | Create a conversation |
| GET | `/api/conversations` | List conversations |
| GET | `/api/conversations/{id}` | Messages and citations |
| DELETE | `/api/conversations/{id}` | Delete messages and associated graph state |
| POST | `/api/conversations/{id}/messages` | Submit one user turn |

Initial message request: `{"content":"Can I appeal this suspension?"}`.
Response: `kind`, `answer`, `citations`, `run_id`, `corpus_commit`, `prompt_version`,
`model`, `provider`, `retrieval_mode`, `model_calls`, `search_calls`, `latency_ms`.
`run_id` identifies the finalized turn. Citation objects include an answer-local label and
the immutable evidence fields. The server builds URLs, not the model.
Start with ordinary JSON responses; add streaming only if needed after validation.
Conversation listings include the first completed question as `title`, plus
`turn_count`. Details expose ordered `turns` containing the original question and
the complete finalized response.

## Frontend and evaluation

The React client sends same-origin `/api` requests through Vite in development and
Nginx in Compose. No model key is exposed to JavaScript. Sources render as escaped
plain text, and final-answer labels open their evidence panels. A process-local
UI request guard prevents duplicate submission and navigation while a turn is active.

`evals/answers.py` validates 45 scenarios with source-text anchors, then optionally
executes real calls with `--live`. It copies the corpus database into a temporary
workspace and isolates evaluation chat state. Reports separate automatic structural
checks from unfilled human semantic reviews. Agent qualitative review is recorded separately in `evals/REVIEW.md`. `evals/README.md` defines the rubric.

## Agent state and controls

- State: messages, current-turn evidence map, search/model-call counts, trace and result.
- SQLite checkpointer keyed by server-created conversation IDs; separate graph store
  from corpus tables. Reset evidence/call budget for every user turn.
- Expose `search_policies(query)` and `submit_answer(kind, answer)`. The second tool
  is a structured final-output channel. No category filter is implemented yet.
- The model can reformulate queries and repeat searches, with at most three searches
  and six model calls per turn by default. A tool batch processes at most four tools.
- `kind=answered` requires current-turn evidence and inline `[[chunk_id]]` markers.
  The server validates IDs, assigns `[1]` labels, and supplies source metadata. It
  rejects unknown IDs, handwritten URLs and malformed citation markers.
- Greeting, clarification, out-of-scope and insufficient-evidence kinds cannot cite
  sources. Their semantic classification is still model-controlled; structural
  checks do not prove grounding or prevent misclassified policy assertions.
- Treat retrieved text as data. Do not follow embedded instructions or arbitrary URLs.
- No model initialization or paid request on import, health checks or corpus indexing.
- Surface missing settings and provider failures as clear errors, never fabricated answers.

Execution: `START → decide → execute → decide/finalize → END`.
Tool and model outputs are checkpointed in `checkpoints.sqlite3`. Canonical completed
turns and run metadata live in `conversations.sqlite3`; the API loads that history
and explicitly replaces all graph state before each new turn. A failed run therefore
cannot inject partially completed tool messages into a retry. Deleted chats remove
turns, run metadata and their graph checkpoints. SQLite file backups/WAL reclamation
are outside the application deletion contract.

Within one service process, locks serialize chat/delete requests per conversation.
Deploy one API worker. The last six completed turns are sent to the model by default;
full history remains stored. No automatic summarization or authentication is implemented.

## Hybrid retrieval

Embedding input contains document title, heading and source text. Cache identity
includes provider, model, base URL and input-format version; each vector also records
its input hash. The manifest stores corpus metadata and dimensions. Builds batch
requests, reuse matching vectors and replace the cache transactionally after all
vectors validate. Corpus replacement invalidates the cache.

Query vectors and cached vectors must be finite, nonzero and dimension-compatible.
Cosine similarity produces the top 20 semantic candidates; FTS5 supplies up to 20
keyword candidates. Reciprocal rank fusion (`1/(60+rank)`) merges their ranks and
returns six chunks by default. Hybrid misconfiguration fails explicitly. Similarity
is not treated as a calibrated confidence score; the agent must inspect the evidence.


## Acceptance-driven refinements

The agent search tool takes the normal six ranked seeds and adds up to four adjacent
chunks from the top three seeds, at most ten chunks per search. Neighbors preserve
their own immutable citation IDs/lines and carry `retrieval_context=true`. This
addresses a measured failure where a definition section was returned but the next
section containing a deadline was missing. The search API and retrieval benchmark
still use ranked seeds without expansion, keeping the comparison consistent.

Prompt v2 asks for focused alternative searches, short answers and no corpus-wide
absence claims based on incomplete retrieval. The original question is stored in
agent state. When the model selects `insufficient_evidence`, the server replaces its
prose with conservative English/Chinese text to avoid uncited policy assertions.
Other semantic mistakes, including selecting `answered` for an unavailable date,
remain possible and are documented in evaluation review.

Compatible embedding requests disable client token-array preprocessing and send
raw strings with `encoding_format=float`. Batch size is configurable; the tested
Beijing model uses 20. Provider identity, endpoint, model and dimensions remain part
of cache compatibility checks. The frontend never receives provider credentials.
