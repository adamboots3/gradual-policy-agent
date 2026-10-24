# Acceptance audit — online-reading revision, 2026-10-24

Current design follows the user's revised scope: web-only temporary conversations
and an agent that chooses and reads policy files directly from GitHub. The local
policy library, embeddings, ingestion/indexing and interactive CLI are removed.

| Requirement | Current implementation | Boundary |
| --- | --- | --- |
| Policy-grounded support | List directory, let the LLM choose/read files, answer from current-turn text | File-selection misses and semantic overstatements remain possible |
| Multi-turn | At most 20 frontend-owned completed pairs; oldest-first context trimming | No summaries or history restoration |
| Source citations | Actual-read IDs, exact selected original lines, immutable commit URLs | Provenance does not prove claim support |
| Agent framework | LangChain tools/model adapters and bounded LangGraph execution | No arbitrary browsing or production authentication |
| Web access | React chat, inline citations, source panel and online-source information | Model/GitHub access is required for policy answers |
| Environment | Locked Python/npm dependencies, native and Compose startup, no policy initialization | Latest executed checks are in VERIFICATION.md; historical remote CI is not a new run |
| Evaluation | Two complete online runs; final 51/51 completed, 50/51 expected kinds, 51/51 provenance | File-selection/semantic issues are documented; independent human review remains open |
| GitHub delivery | Private repository on `main`, with online-reading source, reports and sequence diagram | Reviewers need repository access; check Actions for the published revision |

Repository: [adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent).
The previous web-only commit `4bc4639` passed all five GitHub Actions jobs.
The online-reading change is recorded separately; old reports remain historical.
No public deployment or automatic reviewer invitations were created. Credentials
stay local and are never included in submitted reports.
