# Acceptance audit — 2026-10-22

Core assignment features and local verification are complete. This is a local
submission candidate, with known model-quality limitations. GitHub delivery and
container/remote verification remain outstanding.

| Requirement | Implementation and executed evidence | Remaining limitation |
| --- | --- | --- |
| Policy-grounded support | Pinned 57-document corpus; hybrid retrieval; 51 real answer turns | Semantic review found overstatements; see `evals/REVIEW.md` |
| Multi-turn | Six two-turn eval scenarios; persistent history; actual Chinese browser follow-up | One trademark follow-up unnecessarily refused |
| Source citations | Exact immutable GitHub lines, excerpts, IDs checked; all 51 turns passed provenance validation | Valid provenance does not prove claim support |
| CLI or web interface | Both implemented; six UI tests, production build, actual browser/source interaction | Browser QA at 614px width; desktop visual QA not performed |
| Evaluation suite | 45 scenarios, 51 turns, 36 anchors; three complete real runs and retrieval comparison | Public development set; independent human review not completed |
| Agent framework | LangChain provider/tools + bounded LangGraph state machine | One process/worker; no production authentication |
| Reproducible environment | Python/npm locks, clean environment install, installed-wheel regression: 55 tests | Other OS and Docker runtime verification pending |
| GitHub submission | Local Git repository, CI configuration, sanitized source and reports | No user-provided remote; nothing pushed |

## Before final submission

1. Create an empty GitHub repository and provide its URL. Push the local revision
   once the intended destination is known.
2. Check the actual Windows/Linux and container jobs in GitHub Actions. Resolve
   failures before calling cross-platform/container support verified.
3. Review the live report and known issues. Human semantic-review fields are blank
   deliberately; the coding agent's review is labeled separately.
4. Include the repository URL and setup/demo instructions in the submission.
   Reviewers provide their own model keys; credentials and local databases are ignored.

Docker is not installed on this host. No public deployment or remote repository has
been created. No API keys are part of the handoff.
