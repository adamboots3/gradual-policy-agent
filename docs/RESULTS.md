# Historical evaluation results — 2026-10-22

These real runs predate the 2026-10-24 window-memory/web-only change. They are not
new answer-quality scores for the current online-file-reading architecture.
The local policy library, embeddings and hybrid search described below were removed
on 2026-10-24. See VERIFICATION.md and the online evaluation report for current checks.

## Configuration

Corpus: `b9578b546d2506febda1da2cd7431644d58e512c`, 57 Markdown documents,
721 chunks. Final prompt: `policy-agent-v2`. Chat: DeepSeek `deepseek-flash`,
non-thinking tool calls. Embeddings: Beijing Alibaba Bailian
`qwen3.7-text-embedding-flash`, 1,024-dimensional float vectors, batches of 20.
Hybrid retrieval uses SQLite FTS5 + cosine similarity, merged with reciprocal rank
fusion. Agent search includes bounded adjacent source context.

## Live answers

Each run used the same 45 scenarios / 51 turns, including six multi-turn scenarios.
These are public development cases, not a held-out benchmark. All three reports
contain actual responses, citation excerpts and tool traces. No request errors occurred.

| Run | Expected response-kind agreement | Citation provenance | Policy answers have citations |
| --- | --- | --- | --- |
| Initial keyword / v1 | 48/51 (94.1%) | 51/51 | 51/51 checks passed |
| Keyword / v2 + neighboring context | 50/51 (98.0%) | 51/51 | 51/51 checks passed |
| Final hybrid / v2 + neighboring context | 49/51 (96.1%) | 51/51 | 51/51 checks passed |

For non-policy answers, citation-presence checks pass vacuously. All runs matched the
corpus version. Final mean expected-document and reference-anchor coverage across
the 45 turns with references was 97.8%. Final median latency was 6.02s; maximum
12.84s. This is one sequential run on one host, not a load or latency benchmark.

**These are structural/coverage metrics, not answer accuracy or semantic grounding.**
The final hybrid answer run did not improve kind agreement over keyword v2. Model
sampling and changed retrieval prevent attributing that difference to a single cause.

The initial Chinese appeal question missed the adjacent six-month clause and
incorrectly suggested it was absent. The v2 prompt and bounded neighboring context
recovered that clause in the subsequent keyword and hybrid runs. This is development
iteration on a known failure, not independent validation.

The coding agent inspected all final answers against the case expectations and
reviewed passages for identified issues; [review notes](../evals/REVIEW.md) preserve
missed answers and overstatements. Human review fields remain null. No independent
human accuracy score or calibrated model-judge score is claimed.

## Retrieval comparison

The fixed extended dataset has 24 questions: 12 original English questions, six
English paraphrases and six Chinese queries. Both modes used top-six chunk results,
without the agent's neighboring-context expansion. The metric asks whether each
expected document appeared; it does not measure section coverage or answer quality.

| Queries | Keyword | Hybrid |
| --- | --- | --- |
| English (18) | 16/18 | 16/18 |
| Chinese (6) | 0/6 | 6/6 |
| Total | 16/24 (66.7%) | 22/24 (91.7%) |

Both modes missed the expected dedicated document for `paraphrase-research` and
`paraphrase-copyright`. Related retrieved policies may contain useful information,
but the expected-document metric remains a miss. The original easier 12-English
baseline achieved 12/12 and should not be substituted for this comparison.

Reproduce after corpus sync/index and embedding setup:

```sh
uv run python -m evals.retrieval --dataset evals/datasets/retrieval-extended.jsonl --mode keyword --output evals/reports/retrieval-keyword-extended.json
uv run python -m evals.retrieval --dataset evals/datasets/retrieval-extended.jsonl --mode hybrid --output evals/reports/retrieval-hybrid.json
uv run python -m evals.answers --live --output evals/reports/answers-live.json
```

Hybrid retrieval evaluation calls the embedding API, not the chat API. The live
answer runner calls configured chat and, in hybrid mode, query-embedding APIs.
Charges and free quota depend on the configured provider account; monetary cost was
not independently reconciled. Token metadata is retained when the provider supplies it.

## Environment and interface

- Final installed wheel in a separate Python environment: **55 backend tests passed**.
- Frontend clean locked install, **6 tests**, formatting and TypeScript/production
  build passed. No frontend changes followed that check.
- Real Chinese two-turn browser flow, source switching and reopening saved history
  after refresh verified at 614px width. [Demo](DEMO.md) contains real responses.
- Source revision `b8af71c` is uploaded to the private repository
  [adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent).
- [GitHub Actions run](https://github.com/adamboots3/gradual-policy-agent/actions/runs/39810856851) passed all five jobs: Windows/Linux backend, Windows/Linux frontend,
  and Docker build/start/health smoke. The Docker check does not exercise corpus
  sync/index or paid model calls inside the containers. Docker remains absent locally.

Known application limits include model overstatement, occasional false refusals,
no authentication, bounded model context, a pinned rather than live
policy snapshot, and citations whose semantic support still needs review.
