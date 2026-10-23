# Acceptance audit — updated 2026-10-24 (Asia/Shanghai)

Core assignment features, local verification and private GitHub delivery are complete.
All five GitHub Actions jobs passed for baseline source revision `b8af71c`; the
window-memory/web-only revision has separate local checks recorded in VERIFICATION.md. Known model-quality
limitations and independent semantic review remain documented.

| Requirement | Implementation and executed evidence | Remaining limitation |
| --- | --- | --- |
| Policy-grounded support | Pinned 57-document corpus; hybrid retrieval; 51 real answer turns | Semantic review found overstatements; see `evals/REVIEW.md` |
| Multi-turn | Window-owned temporary context; fresh per-request graph; no persistent history | One trademark follow-up unnecessarily refused |
| Source citations | Exact immutable GitHub lines, excerpts, IDs checked; all 51 turns passed provenance validation | Valid provenance does not prove claim support |
| Web interface | Web chat only; CLI chat removed by revised user scope; window isolation/reset tests | 1280×720 temporary-chat flow and reset verified; latest narrow-screen behavior covered by responsive CSS/component checks |
| Evaluation suite | 45 scenarios, 51 turns, 36 anchors; three complete real runs and retrieval comparison | Public development set; independent human review not completed |
| Agent framework | LangChain provider/tools + bounded LangGraph state machine | One process/worker; no production authentication |
| Reproducible environment | Python/npm locks; new clean environment without SQLite checkpointer; 63 backend tests and 11 frontend tests passed | Windows/Linux CI and Docker build/start/health passed; containerized corpus/model execution untested |
| GitHub submission | Private `adamboots3/gradual-policy-agent`, `main`, source revision `b8af71c` uploaded | Reviewers need private-repository access |

## Delivery evidence

Repository: [adamboots3/gradual-policy-agent](https://github.com/adamboots3/gradual-policy-agent),
private, default branch `main`. Created using the user's existing account, matching
visibility of the other assignment repository. Source revision: `b8af71c`.

[GitHub Actions run](https://github.com/adamboots3/gradual-policy-agent/actions/runs/39810856851): all five jobs passed:
Windows/Linux backend, Windows/Linux frontend and Docker build/start/health smoke.
Containerized corpus sync/index and paid model execution were not part of the smoke
check; those paths were exercised natively on Windows. Docker is absent locally.

## Final reviewer handoff

- Include the repository URL and grant the intended reviewers access to the private
  repository. Do not make it public or invite arbitrary accounts automatically.
- Review the live report and known issues. Human review fields are blank deliberately;
  the coding agent's qualitative review is labeled separately.
- Reviewers supply their own model keys; credentials and local databases are ignored.
  No API keys were uploaded and no GitHub Actions secrets were needed.

No public application deployment has been created. The repository contains native
and Compose startup instructions, actual demonstration screenshots and evaluation reports.
