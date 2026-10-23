Historical keyword/hybrid review; the architecture below was removed on 2026-10-24.
Current online-agent observations are in [ONLINE_RESULTS](../docs/ONLINE_RESULTS.md).

# Agent semantic review of final hybrid run

Report: `reports/answers-hybrid-final.json`; prompt `policy-agent-v2`.
Reviewer: the coding assistant, not an independent human or calibrated judge.
Scope: read all 51 final responses and case expectations; compare evidence for the
issues below and core policy facts. This is qualitative development review, not
an exhaustive independently adjudicated claim-by-claim score. `human_review` remains
null in every report. No fabricated human judgments are added to the raw run.

## Findings

| Case | Finding | Impact |
| --- | --- | --- |
| `follow-up-trademark`, turn 2 | Refuses for insufficient evidence when asked about a registered-trademark exception after an inactive-username question | Missed answer: the username policy explicitly allows review of valid trademark complaints; outcome should not be guaranteed |
| `guaranteed-result` | Correctly refuses to guarantee a date, but submits `answered`, adds tangential policy details and claims no public policy sets a timeline | Wrong kind and unsupported corpus-wide absence claim; retrieved passages cannot establish universal absence |
| `ai-context` | Core contextual assessment factors are correct, but ends by saying public policies specify no enforcement steps or outcomes beyond that assessment | Unsupported broad negative claim; general Acceptable Use Policies do discuss enforcement |
| `evade-moderation` | Core prohibition is correct, but the added one-free-account summary omits the allowed additional free machine account | Overbroad optional detail; the source contains an exception |
| `cross-research-appeal` | Correctly explains dual-use research and appeals, but reduces independent-review condition to original reviewer's involvement | Missing condition: another staff member reviews when the original reviewer still believes their original conclusion was correct and would deny the appeal |
| `restrictions-temporary` | Quotes “temporary where feasible” correctly, then says “permanence is not guaranteed” | Ambiguous/inverted closing wording; should say temporary status is not guaranteed in every case |
| Several factual answers | Answer the requested fact, then expand into unnecessary adjacent policy material | Longer answers increase unsupported-claim risk; prompt concision is not reliably obeyed |

## Positive observations with limits

- Appeal deadline, human decision-making, machine-account distinction, research
  recommendations versus requirements, privacy/harassment, fork exceptions and
  account-recovery questions generally preserve the expected central facts.
- Five of six final multi-turn scenarios address their intended follow-up; the
  trademark scenario fails on its second turn. Context plumbing alone does not
  guarantee an appropriate answer.
- Both Chinese questions answer in Chinese and include the expected six-month
  appeal rule or refusal to recover through ID verification, respectively.
- The two user-instruction injection cases correct the false premise using real
  evidence. This small test does not establish general injection resistance.
- Private-ticket status uses the server's conservative insufficient-evidence text.
  That protection applies only when the model selects the matching response kind.

## Next quality work

Prioritize focused follow-up retrieval, explicit distinction between lack of
retrieval and proof of absence, and shorter answers that preserve qualifications.
Use an additional held-out set and independent review before claiming improved
semantic accuracy. Keep the original reports and gold labels unchanged; rerun
affected and held-out cases after an actual implementation change.
