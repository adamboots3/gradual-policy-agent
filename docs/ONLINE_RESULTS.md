# Recorded online-agent evaluation — 2026-10-24

Report: [answers-online.json](../evals/reports/answers-online.json).
Dataset: [answers.yaml](../evals/datasets/answers.yaml), version 1.
The run used `policy-agent-online-v2`, 45 scenarios / 51 turns / 36 reference
anchors, and policy commit `b9578b546d2506febda1da2cd7431644d58e512c`.
The configured model was `deepseek-flash` through a generic compatible adapter;
the application architecture is provider-independent. Three isolated workers ran
the scenarios. Reference texts and expected paths were not given to the agent.

## Results and interpretation

| Metric | Recorded result | Meaning |
| --- | --- | --- |
| Completed turns | 51/51; zero request errors | All requested turns produced checkable responses |
| Expected-kind agreement | 50/51 | Response classification matched the case expectation |
| Citation provenance | 51/51 | Cited original text, lines, links and current-turn reads matched |
| Policy-answer citation checks | 51/51 | Answers classified as policy answers contained citations |
| Source-version checks | 51/51 | References used the fixed evaluation snapshot |
| Mean expected-document coverage | 94.4% | Coverage of expected files on turns with reference expectations |
| Mean reference-anchor coverage | 92.2% | Coverage of expected original passages on those turns |
| Request latency | Median 7.50s; maximum 14.17s | One run at three workers; not a load benchmark |

These are structural and evidence-location metrics, **not answer accuracy**.
Non-policy replies require no citations, so some checks pass without source reads.
A correct alternative source can have low expected-anchor coverage; a genuine
citation can still be interpreted incorrectly. The public development set is not
a held-out benchmark, and `human_review` fields remain null.

## Known semantic findings

- `guaranteed-result`: declines to guarantee a date but classifies a policy
  overview as `answered`; the expected kind is `insufficient_evidence`.
- `research-contact`: misses the malware-policy contact recommendation and makes
  an overly broad claim from the disclosure/SIRT files it selected.
- `evade-moderation`: gives a plausible conclusion with account-count/inauthentic
  activity evidence instead of the explicit moderation-evasion provision.
- `cross-copyright-trademark`: uses Trademark Policy and the general removal
  request policy instead of the expected DMCA source; the distinction needs review.
- `false-age`: adds a country-specific qualification without its own supporting citation.
- Browser checks have also exposed unnecessary overviews and overly broad wording
  around Appeal versus Reinstatement. Conditions and deadlines need careful review.
- During the maintenance smoke check, a greeting after policy discussion was
  treated as a continuation of the prior policy question. A fresh-window greeting
  worked correctly; context-following reliability still needs semantic evaluation.

This report is retained unchanged as an observed run, not relabeled as a new score
after maintenance. Semantic accuracy has not been independently adjudicated.
Earlier experiments are available in Git history; the current tree retains only
the online-agent dataset and recorded report. See [evaluation instructions](../evals/README.md)
for new runs and [verification](VERIFICATION.md) for current engineering checks.
