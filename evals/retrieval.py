import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from policy_agent.config import Settings
from policy_agent.retrieval import corpus_status
from policy_agent.semantic import Retriever


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("evals/datasets/retrieval.jsonl"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mode", choices=["keyword", "hybrid"], default="keyword")
    args = parser.parse_args()
    settings = Settings()
    settings = settings.model_copy(update={"retrieval_mode": args.mode})
    retriever = Retriever(settings)
    status = corpus_status(settings.database)
    if not status["chunks"]:
        parser.error("Index the pinned corpus before evaluating")
    cases = []
    for line in args.dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        results = retriever.search(case["query"], 6)
        retrieved = {row["path"] for row in results}
        expected = set(case["expected_paths"])
        recall = len(expected & retrieved) / len(expected)
        cases.append(
            {
                **case,
                "recall_at_6": recall,
                "retrieved_paths": list(dict.fromkeys(row["path"] for row in results)),
            }
        )
    if not cases:
        parser.error("Evaluation dataset must contain at least one case")
    report = {
        "evaluation": f"{args.mode}-document-recall",
        "live_model": args.mode == "hybrid",
        "embedding_provider": settings.embedding_provider if args.mode == "hybrid" else None,
        "embedding_model": settings.embedding_model if args.mode == "hybrid" else None,
        "timestamp": datetime.now(UTC).isoformat(),
        "corpus": status,
        "cases": cases,
        "mean_recall_at_6": sum(c["recall_at_6"] for c in cases) / len(cases),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
