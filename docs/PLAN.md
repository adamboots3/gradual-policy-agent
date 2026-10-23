# Implementation plan and current scope

## Current architecture

LangChain tools/providers, a bounded LangGraph controller, FastAPI and React/TypeScript.
The agent browses the GitHub policy directory and reads selected files online.
SQLite policy storage, FTS/vector search, document chunking, Embedding configuration
and initialization commands were removed at the user's request on 2026-10-24.

## Agreed decisions

- Web access only. The current page holds temporary completed question/answer pairs.
- Use the frontend's most recent 20 completed pairs, trimming oldest whole pairs
  only when context budgeting requires it; recheck before each model call.
- Three tools: list directory, read selected original files/ranges, submit answer.
- Let the LLM select files by directory/name and continue reading when needed.
- Pin one immutable GitHub commit per question; keep bodies only in request memory.
- Build exact original-line citations from ranges read in this question. Do not
  treat earlier answers as policy evidence or provenance as semantic correctness.
- Fail explicitly on source/network/rate-limit errors rather than inventing policy.
- No saved chat history, embedding service, local policy library, automatic summaries,
  authentication, admin system or public deployment.

## Validation and handoff

Verify source access, bounded tools, citation ranges, context trimming/isolation,
frontend behavior and clean setup. The 45-scenario / 51-turn suite has been rerun for this architecture, including
a complete initial run and a revised numbered-citation run; both reports are retained. Record actual results and
limitations in VERIFICATION.md and evaluation documentation. Independent human
semantic review remains open; no scripted test or coverage number is an accuracy score.

The prior web-only revision was delivered to the private repository. This online
reading revision is local until explicitly pushed; GitHub CI results for older
commits do not verify the new source.
