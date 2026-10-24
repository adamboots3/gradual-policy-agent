# Evaluation suite

[English](README.md) | [简体中文](README.zh-CN.md)

## Deterministic tests

```sh
uv run pytest
```

Tests execute the graph and source reader with scripted models and mocked GitHub
responses. They require no network or model keys and do not measure model quality.

## Validate the dataset against GitHub

```sh
uv run python -m evals.answers --validate
```

This reads GitHub but makes no model calls. It validates the schema, unique case
IDs, reference IDs, immutable policy commit and exact original excerpts.
`corpus_commit` in the dataset names the remote policy snapshot, not a local
database. The fixed set contains 45 scenarios / 51 turns / 36 source anchors,
including six multi-turn scenarios, factual/cross-document questions, false
premises, insufficient evidence, out-of-scope requests, injection and Chinese.
An optional read-only `POLICY_GITHUB_TOKEN` raises the public REST API quota.

## Live evaluation

```sh
uv run python -m evals.answers --live --limit 3 --output evals/reports/answers-smoke.json
uv run python -m evals.answers --live --workers 3 --output evals/reports/answers-local.json
```

A configured tool-capable chat model is required; live calls incur provider costs.
The default output is `evals/reports/answers-local.json`, which is Git-ignored and
does not overwrite the committed baseline. `--workers 1..4` runs isolated scenarios
(default 1); result ordering remains fixed. Different concurrency levels do not
provide a controlled latency comparison.

The runner pins the dataset's policy commit and calls the same `ChatService` as
the API. Each question creates a fresh reader; the LLM chooses and opens files.
Only completed question/answer pairs pass to later turns of the same scenario,
capped at 20. Context resets between scenarios. A failed setup turn stops dependent
follow-ups. Reference text stays in evaluator memory and is never supplied to the
agent; alternative cited files are independently fetched for checking.

Reports contain questions, responses, exact citations, traces, version/model/prompt
metadata, usage, latency and error types. They contain no credentials. Only explicit
synthetic evaluation reports are written; application chat and source caches remain
temporary. Generated reports stay ignored until deliberately selected for version control.

## Metrics and semantic review

Automatic checks measure expected-kind agreement, exact citation provenance,
current-turn reads, citation presence, source version and expected file/anchor
coverage. **They are not answer accuracy or proof of semantic support.** Non-policy
answers can pass citation checks without reads; valid alternative evidence can
have low expected-source coverage.

Review `human_review.correctness`, `grounding`, `citation_support` and `notes` for
each turn. Check the exact question, follow-up interpretation, exceptions and
whether every material claim follows from its cited lines. For non-policy replies,
grounding/support may be inapplicable, but response appropriateness still matters.
Leave unreviewed fields null; distinguish coding-agent observations from independent
human assessment. No model-judge prompt is implemented.

The dataset is public development data. Prompt, model or source-reading changes
require a new live run before claiming a new quality score. The unchanged
[recorded report](reports/answers-online.json) and its known failures are described
in [ONLINE_RESULTS](../docs/ONLINE_RESULTS.md); current engineering checks are in
[VERIFICATION](../docs/VERIFICATION.md).
