# Architecture and contracts

## Current interaction model — 2026-10-24

Web access only. The page owns completed turns in React memory; the server has no
conversation store, session identifier, shared chat memory or persistent checkpointer.
New tabs are empty. New chat, refresh, navigation away or window closure clears the
page state. Page exit aborts the client request and invalidates late responses; the
server may finish an already-running request, but never saves its dialogue.

```mermaid
sequenceDiagram
    autonumber
    box rgb(219,234,254) Starting point
        participant U as User
    end
    participant W as Current chat window
    participant B as FastAPI
    box Agent execution
        participant A as LangGraph controller
        participant L as Configurable LLM
    end
    box Policy retrieval
        participant R as Retrieval tool
        participant E as Configurable embeddings
        participant K as Policy index
    end
    U->>W: Ask or follow up
    W->>B: Question + temporary completed context
    B->>A: Process this request
    A->>L: Context and tool descriptions
    L-->>A: Request policy search
    A->>R: Execute search query
    R->>E: Embed query text
    E-->>R: Query vector
    R->>K: Keyword and vector search
    K-->>R: Policy candidates
    R->>R: Fuse ranks and add neighboring clauses
    R-->>A: Evidence and source IDs
    A->>L: Supply retrieved evidence
    L-->>A: Submit answer and citation IDs
    A->>A: Validate IDs and build citation links
    A-->>B: Final response
    B-->>W: Answer and source excerpts
    W->>W: Update temporary in-window context
    W-->>U: Display answer
```

The diagram describes the common hybrid path. Keyword mode omits query embeddings;
the model can search again within its budget or request clarification. Document
vectors are built ahead of time, not regenerated per question. Citation checking is
code inside the agent's submit-answer handling, not a separate AI verifier.

## Evidence and retrieval

`corpus.lock.json` fixes the Git source commit. Parsing preserves title, heading,
path, original line range, content hash and immutable GitHub URL. Chunk IDs include
source identity. Index replacement is transactional; dirty or mismatched source is
rejected. SQLite stores policy chunks, FTS5 and cached embeddings only.

Hybrid retrieval fuses up to 20 keyword and 20 semantic candidates using
`1/(60+rank)`, normally returning six seeds. The agent's search tool adds up to four
neighboring chunks from the top three seeds; at most ten pieces of evidence per
search. The public search API and retrieval benchmark do not add neighbors.

Embedding identity includes provider, model, endpoint, input hash and dimensions.
Incompatible indexes fail explicitly. Compatible adapters send raw text and request
float vectors. Chat and embedding services are independently configurable.

## Request-scoped agent

`ChatService.chat(question, history)` creates a fresh graph invocation. History is
caller-owned, limited to completed question/answer pairs, at most 20 pairs. All
supplied pairs are used when they fit. It is never used as policy evidence. No model
initialization or paid request occurs at import, health checks or corpus indexing.

Before every model call, `ContextBudget` estimates input tokens for system text,
tool definitions, history, the current question and all current-turn messages. It
subtracts the configured output cap and safety margin from the model's context
capacity. It drops oldest **whole question/answer pairs** until the input fits.
The next call after retrieval repeats this check; AI tool calls and their matching
results remain together, with the current question and agent execution intact.
History from an earlier request's agent execution is never imported.

Capacity comes from `POLICY_CHAT_CONTEXT_WINDOW_TOKENS`, or (when zero) LangChain's
model profile, with a documented 32,768-token fallback for unknown models. Output
defaults to 2,048 tokens (also passed to the model as `max_tokens`); the default
margin is 512. Token counting is a local LangChain approximation with a UTF-8
allowance, not an exact vendor tokenizer. Recognized provider context errors drop
one more oldest pair and retry until accepted or no history remains. No network,
authentication or rate-limit errors trigger this retry. If mandatory current-turn
material cannot fit without history, return 422 instead of breaking tool messages
or fabricating a policy refusal. No automatic summaries are created.

The model calls `search_policies` and `submit_answer`; defaults are three searches
and six successful model responses per turn. Overflow retries are additionally
bounded by the at-most-20 historical pairs and appear in explicit evaluation traces.
State includes messages, remaining history count, evidence, counts and an
in-memory trace. Errors do not leave a partial turn behind. Separate requests do
not share messages, evidence or budgets; conversation locks are no longer needed.

Answered policy claims require current-turn retrieved IDs. The server rejects
unknown IDs, malformed markers and handwritten links, then creates numbered links
and exact excerpts. This checks provenance, not semantic support. For
`insufficient_evidence`, conservative localized text replaces model prose. Semantic
classification and unsupported generalizations remain known model-quality risks.

## API

| Method | Path | Contract |
| --- | --- | --- |
| GET | `/api/health` | Process/configuration status; `conversation_mode=window-memory` |
| GET | `/api/knowledge` | Source commit, document/chunk counts |
| POST | `/api/knowledge/search` | `{query, limit}` to inspect ranked evidence |
| POST | `/api/chat` | `{content, history:[{question,answer}]}` to process one turn |

All former `/api/conversations` create/list/get/delete/message routes are removed.
History fields are bounded (question 1–4,000 chars, answer 1–6,000 chars); role/tool
fields cannot be injected through the context schema. Empty requests or overlong
context return 422. Chat responses, including errors, use `Cache-Control: no-store`.
No cookies or browser local/session storage are used. The frontend blocks duplicate
submissions and clearing while a request is pending; it aborts and ignores responses
on page exit. Network retries cannot append to a hidden server-side conversation.

## Diagnostics, evaluation and scope

Responses include model/prompt/corpus metadata, request run ID, counts and latency,
plus received/used/trimmed history counts. Trimming changes only LLM input, not
frontend display state; each new request starts from that request's supplied pairs.
Run IDs are diagnostic labels, not database keys. No ordinary chat/run/checkpoint
record is written. Explicit evaluations request a transient trace and write their
synthetic cases to reports; context resets between scenarios. Corpus copies keep
evaluation evidence stable.

Policy initialization uses `python -m policy_agent.setup {sync,index,embed,status}`.
There is no CLI chat or resumable terminal conversation. No authentication, admin
console or automatic summarization is included. Historical live reports and demo
captures predate this revised window-only interaction model.
