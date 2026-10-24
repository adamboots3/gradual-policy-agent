# Current capability and validation status

The application is a web-only GitHub policy assistant. It reads original policy
files online through a bounded LangChain/LangGraph agent and keeps conversation
history only in the current browser page.

| Capability | Implementation | Validation and limits |
| --- | --- | --- |
| Policy source | Directory-guided selection and original-line reads from `github/site-policy` | One immutable commit per request; exact blob checks; source failures abort |
| Multi-turn context | Frontend sends up to 20 completed pairs | Rechecked before every model call; oldest whole pairs trimmed; no summaries |
| Temporary state | Fresh graph, evidence and reader per request | Window/request isolation, no chat storage, no old tool traces imported |
| Citations | Server extracts selected original lines and builds commit/line URLs | Format, current reads and ranges validated; semantic support still needs review |
| Agent control | Three tools, three graph nodes, conditional routing | Default six read attempts, two directory requests, ten successful model responses |
| Web UI | Questions, follow-ups, citations, reset and recoverable errors | 14 frontend tests; real Chinese follow-up/source/reset checks; no CLI chat |
| API | Health, source configuration and stateless chat | 79 backend tests; unknown fields rejected; sanitized source/model failures |
| Evaluation | Fixed 45-scenario / 51-turn / 36-anchor dataset | Online recorded run retained unchanged; independent semantic review incomplete |
| Reproducibility | Locked Python/npm dependencies, native and Compose startup | Windows/Linux and container checks are automated in GitHub Actions |

Current execution evidence is in [VERIFICATION](VERIFICATION.md). The
[recorded evaluation](ONLINE_RESULTS.md) includes file-selection and interpretation
failures; source provenance is not answer accuracy. The app has no authentication
or public hosting configuration. Source is available in the public
[source repository](https://github.com/adamboots3/gradual-policy-agent).
