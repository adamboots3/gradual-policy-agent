# Evaluation suite

[English](README.md) | [简体中文](README.zh-CN.md)

## Deterministic checks

```sh
uv run pytest
```

Tests use mocked GitHub APIs and scripted model responses. They require no network,
model key, local corpus, index or Embedding service.

## Validate the source-anchored dataset

```sh
uv run python -m evals.answers --validate
```

This makes GitHub read requests but no model calls. It validates the schema, unique
case/reference IDs, the immutable policy commit and exact reference excerpts from
GitHub. No local policy checkout or database is used. Optional `POLICY_GITHUB_TOKEN`
provides higher read API limits. The suite contains 45 scenarios / 51 user turns,
including six multi-turn scenarios, cross-document questions, false premises,
missing evidence, out-of-scope requests, injection and Chinese questions.

## Live online-agent evaluation

```sh
uv run python -m evals.answers --live --limit 3 --output evals/reports/online-smoke.json
uv run python -m evals.answers --live --workers 3 --output evals/reports/answers-online.json
```

Requires a configured tool-capable chat model and incurs model API costs. The
runner fixes `POLICY_GITHUB_REF` to the dataset commit for comparison. It uses the
same online ChatService: each question starts a new reader and the LLM chooses
files using the directory, then reads them through tools. Earlier answers provide
only temporary scenario context, capped at 20 pairs. Context resets per scenario.
Optional `--workers 1..4` runs isolated scenarios
concurrently (default 1); output ordering stays fixed. Latency from different worker
counts is not a direct performance comparison.
A failed setup turn stops dependent follow-ups.

Gold reference texts are downloaded into evaluator memory solely for validation;
they are never given to the agent. Alternative cited files are independently read
from the same snapshot for checking. No policy bodies or embeddings are persisted
as application data. Only explicit synthetic evaluation reports are written.
Reports record the policy commit, prompt/model, read traces, exact citations, usage,
latency and errors, without keys or endpoint credentials. Generated reports are
ignored until reviewed and explicitly selected for version control.

Automatic checks measure expected-kind agreement, exact original-text provenance,
current-turn read provenance, citation presence, source version and expected anchor
coverage. **These are not answer accuracy or proof of semantic grounding.** A
correct alternative source can have low expected-anchor coverage; a perfectly
formatted citation can support an incorrect interpretation.

## Semantic review

For each completed turn, review `correctness`, `grounding`, `citation_support` and
`notes`. Correctness asks whether the answer addresses the exact question, preserves
exceptions and handles follow-ups. Grounding asks whether every material policy
claim follows from read text. Citation support asks whether the selected lines
actually substantiate each associated claim. For non-policy replies, grounding and
support may be not applicable; correctness still assesses whether refusal/greeting
was appropriate. Keep unreviewed fields null. Coding-agent review is identified
separately from independent human review.

The case set is public development data, not a held-out benchmark. Changes to
prompts, file-reading behavior, model or source require a new run. Prior keyword /
hybrid reports, retrieval datasets and [historical analysis](../docs/RESULTS.md)
remain evidence about the removed architecture; the retrieval runner and embedding
setup no longer exist. Their scores must not be presented as online-agent scores.


## Current recorded online results

The revised numbered-citation agent completed all 51 turns without request errors.
Expected-kind agreement was 50/51; provenance/citation-presence/source-version checks
passed 51/51. Expected-document coverage was 94.4%, anchor coverage 92.2%.
These are not semantic accuracy scores. Initial failures and final limitations are
preserved in [online results](../docs/ONLINE_RESULTS.md) and both raw online reports.
