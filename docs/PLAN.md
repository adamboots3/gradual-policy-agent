# Project scope and design decisions

## Runtime architecture

React/TypeScript provides the web interface; FastAPI hosts a request-scoped
LangGraph agent. LangChain adapts the configured chat model and exposes three
tools: list the GitHub policy directory, read selected original lines, and submit
an answer with citations. The LLM chooses which files and ranges to read.

## Context and source ownership

- The page retains completed turns in React memory. Refresh, page exit and New
  conversation clear them; another tab starts independently.
- The frontend sends at most 20 completed question/answer pairs. Before every
  model call, the backend removes oldest whole pairs only when the input budget
  requires it. The current question and current-turn tool messages remain intact.
- Each question resolves one immutable policy commit. Directory/file caches and
  evidence belong only to that request and are released afterwards.
- Source links and exact excerpts are constructed by the server from lines read
  in the current question. Earlier answers cannot authorize new citations.
- Model, directory and read budgets bound the agent loop. Source failures produce
  explicit errors; unsupported submissions receive tool feedback for correction.

## Validation and limits

Deterministic tests cover the real graph, mocked source access, context boundaries,
citation validation, request isolation and web interaction. The live evaluation
uses 45 scenarios / 51 turns with fixed source anchors. See
[verification](VERIFICATION.md), [evaluation](../evals/README.md) and
[recorded results](ONLINE_RESULTS.md).

Citation provenance does not prove semantic support. Independent semantic review
is still incomplete, and known file-selection/interpretation failures remain
documented. Authentication, public hosting, automatic summaries, persisted chats
and local policy indexing are outside the current scope.
