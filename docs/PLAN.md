# Implementation plan and final status

## Agreed architecture

LangChain model/tool integration, a bounded LangGraph agent, FastAPI, React/TypeScript,
SQLite persistence, keyword + semantic retrieval, source citations and reproducible
evaluation. Hosted configurable model APIs keep reviewers free of GPU requirements.
Chat and embeddings use separate credentials. Tests require neither credential.

## Milestones

| Milestone | Status and evidence |
| --- | --- |
| Reproducible foundation | Python 3.12, uv/npm locks, native setup and CI; clean environment install and final installed-wheel tests passed |
| Pinned corpus | 57 documents / 721 chunks; all source line ranges verified; dirty/mismatched source rejected |
| Hybrid retrieval | DeepSeek chat + Beijing Bailian `qwen3.7-text-embedding-flash`; 721 vectors of 1,024 dimensions; same-set retrieval improved from 16/24 to 22/24 |
| Conversational agent | Bounded tools, canonical completed history, per-chat locking, checkpoint cleanup and immutable citations implemented |
| Answer evaluation | 45 cases / 51 turns executed in three full runs; structural checks and candid agent semantic review committed |
| Web/CLI | Both implemented; real Chinese follow-up, citation inspection and history reopening verified in browser; six UI tests and production build passed |
| Review handoff | Docs, real demo, reports, Docker/CI configuration prepared; final backend regression: 55 passed |

## Acceptance boundaries

- The final live run has two response-kind mismatches, including one missed
  trademark follow-up. Additional semantic overstatements remain documented.
- The coding agent reviewed outputs; independent human review is still open.
  Citation syntax and expected-document recall are not answer correctness scores.
- Docker, another operating system and GitHub Actions have not been executed here.
- Git is initialized locally. GitHub delivery awaits the user's repository URL.
  Do not invent a remote or claim a submitted revision without a successful push.

## Decisions retained

- Lock the corpus; do not update evidence silently at application startup.
- Retain a keyword baseline. Use reciprocal rank fusion without a reranker for this
  scope; measured hybrid gains justify the extra provider, while two retrieval misses
  remain visible. A reranker would need a new comparison rather than an assumption.
- Agent search adds bounded neighboring source chunks to recover adjacent clauses.
- Keep one API worker and the last six completed turns in model context. Full history
  is persisted; no summarization, authentication or admin system in this assignment.
- Never count scripted tests or retrieval coverage as live answer quality.
- Keep failed evaluation cases and disclose limitations rather than editing gold
  labels to improve a score.
