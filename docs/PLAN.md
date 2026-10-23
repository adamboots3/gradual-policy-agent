# Implementation plan and final status

## Agreed architecture

LangChain model/tool integration, a bounded LangGraph agent, FastAPI, React/TypeScript,
SQLite policy storage, keyword + semantic retrieval, source citations and reproducible
evaluation. Hosted configurable model APIs keep reviewers free of GPU requirements.
Chat and embeddings use separate credentials. Tests require neither credential.

## Milestones

| Milestone | Status and evidence |
| --- | --- |
| Reproducible foundation | Python 3.12, uv/npm locks, native setup and CI; clean environment install and final installed-wheel tests passed |
| Pinned corpus | 57 documents / 721 chunks; all source line ranges verified; dirty/mismatched source rejected |
| Hybrid retrieval | DeepSeek chat + Beijing Bailian `qwen3.7-text-embedding-flash`; 721 vectors of 1,024 dimensions; same-set retrieval improved from 16/24 to 22/24 |
| Conversational agent | Bounded tools, window-owned completed context, request-scoped graph and immutable citations; persistent history removed at user request on 2026-10-24 |
| Answer evaluation | 45 cases / 51 turns executed in three full runs; structural checks and candid agent semantic review committed |
| Web access | Web chat only; terminal chat removed at user request. New tabs, refresh and window closure discard context; initialization scripts remain |
| Review handoff | Docs, real demos and reports prepared; baseline private GitHub delivery/CI passed. Revised web-only checks recorded in VERIFICATION.md |

## Acceptance boundaries

- The final live run has two response-kind mismatches, including one missed
  trademark follow-up. Additional semantic overstatements remain documented.
- The coding agent reviewed outputs; independent human review is still open.
  Citation syntax and expected-document recall are not answer correctness scores.
- Windows/Linux backend and frontend checks plus Docker build/start/health smoke
  passed in GitHub Actions. Containerized corpus/model execution remains untested.
- Source revision `b8af71c` was pushed to `adamboots3/gradual-policy-agent` on `main`,
  a private repository created at the user's request on 2026-10-23 (Asia/Shanghai).

## Decisions retained

- Lock the corpus; do not update evidence silently at application startup.
- Retain a keyword baseline. Use reciprocal rank fusion without a reranker for this
  scope; measured hybrid gains justify the extra provider, while two retrieval misses
  remain visible. A reranker would need a new comparison rather than an assumption.
- Agent search adds bounded neighboring source chunks to recover adjacent clauses.
- Revised scope (2026-10-24): retain the last six completed turns in model context
  by default, supplied from page memory. No chat persistence or CLI conversation
  interface; no summarization, authentication or admin system.
- Never count scripted tests or retrieval coverage as live answer quality.
- Keep failed evaluation cases and disclose limitations rather than editing gold
  labels to improve a score.
