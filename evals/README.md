# Evaluation suite

## No paid calls

```sh
uv run pytest
uv run python -m evals.answers --validate
uv run python -m evals.retrieval --output evals/reports/retrieval.json
```

`--validate` is also the default for the answer runner. It checks the dataset schema,
case IDs, reference IDs, clean source commit and exact source excerpts. Run corpus
sync first. The suite has 45 scenarios and 51 user turns, including six multi-turn
conversations, cross-document comparisons, false premises, missing evidence,
out-of-scope questions, instruction injection and Chinese questions.

The reference catalog anchors expected facts to exact text in the pinned corpus.
The answers in `facts` are review guidance, not exact-match strings. Coverage of an
anchor is useful evidence-location feedback; a valid alternative supporting passage
can still be correct and should be noted by the reviewer. This is a public development
set, not a held-out benchmark or proof of generalization.

## Real model evaluation (requires configuration and incurs charges)

```sh
uv run python -m evals.answers --live --limit 3 --output evals/reports/smoke-live.json
uv run python -m evals.answers --live --output evals/reports/answers-live.json
```

The runner snapshots the indexed SQLite corpus into an isolated temporary data
directory; it does not add evaluation chats to workspace history. Each scenario gets
its own conversation, preserving context between that scenario's turns. An upstream
error stops dependent follow-ups in that scenario. Temporary conversations and
checkpoints are deleted. Reports record the corpus, chat/embedding models, retrieval
mode, per-turn prompt version, tool traces, token usage when available and latency.
No API keys or endpoints are included in the report. Generated reports are ignored
by Git until sanitized and deliberately selected for submission.

Automatic checks report response-kind agreement, exact citation provenance,
presence of citations on policy answers, corpus version and expected reference
coverage. They do **not** determine whether the response is factually correct,
whether each claim is supported or whether a refusal is appropriate.

## Human review rubric

For every completed turn, fill in `human_review` in a copy of the JSON report:

| Field | Pass when | Fail when |
| --- | --- | --- |
| correctness | The answer addresses the question and preserves exceptions and uncertainty | Wrong rule, unsupported certainty, missed condition, or wrong follow-up context |
| grounding | All material policy claims follow from the supplied evidence | Invented rule, external knowledge presented as corpus fact, or missing evidence |
| citation_support | Each material claim points to an actually supporting passage | Unrelated passage, unsupported citation, or incomplete claim coverage |
| notes | Explain disagreements or valid alternative evidence | Leave no explanation for a failure |

Use `pass`, `fail`, or `not_applicable`; leave unreviewed values `null`. For a
non-policy response, grounding/citation support may be not applicable, while
correctness still assesses the response's appropriateness. Review injection cases
semantically: a schema-valid greeting can still hide an unsupported policy claim.

No semantic score is published until review is complete. Rerun after changes to
prompts, models, embeddings, chunking or the policy snapshot; compare failures rather
than relying only on one aggregate number. Three complete live runs are now committed. See the results below.


## Recorded results

The final `reports/answers-hybrid-final.json` run completed 51/51 turns without
provider errors: expected-kind agreement 49/51, provenance 51/51 and corpus version
51/51. Citation presence passed for all policy answers; non-policy answers pass that
check vacuously. The initial keyword and revised keyword reports are also retained.
These metrics are not answer accuracy. [Agent review](REVIEW.md) records semantic
problems separately and leaves the raw `human_review` fields unfilled.

On the same 24-question extended retrieval dataset, keyword achieved 16/24 expected
document hits and hybrid 22/24; Chinese subsets were 0/6 and 6/6 respectively.
Use `--dataset evals/datasets/retrieval-extended.jsonl --mode keyword` or `--mode hybrid`
with the retrieval runner to reproduce. Hybrid makes paid embedding calls; its
`live_model` flag refers to embeddings, not generated answers. The default runner
remains the original 12-question keyword baseline.

[Full methodology, comparison and limits](../docs/RESULTS.md).
