"""Source-anchored cases; structural metrics and human quality review stay separate."""

import argparse
import json
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from policy_agent.chat import ChatService, HistoryTurn
from policy_agent.config import Settings
from policy_agent.ingestion import git
from policy_agent.providers import create_chat
from policy_agent.retrieval import corpus_status
from policy_agent.storage import connect
from pydantic import BaseModel, Field, model_validator

KINDS = Literal["answered", "clarification", "out_of_scope", "greeting", "insufficient_evidence"]


class Reference(BaseModel):
    path: str
    contains: str = Field(min_length=5)


class EvalTurn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    expected_kinds: list[KINDS] = Field(min_length=1)
    references: list[str] = Field(default_factory=list)
    facts: list[str] = Field(min_length=1)


class EvalCase(BaseModel):
    id: str
    category: Literal[
        "factual",
        "multi_turn",
        "cross_document",
        "false_premise",
        "insufficient",
        "out_of_scope",
        "injection",
        "multilingual",
    ]
    turns: list[EvalTurn] = Field(min_length=1)


class Dataset(BaseModel):
    version: int
    corpus_commit: str
    references: dict[str, Reference]
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def check_references(self):
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Case IDs must be unique")
        for case in self.cases:
            for turn in case.turns:
                if any(key not in self.references for key in turn.references):
                    raise ValueError(f"Unknown reference in {case.id}")
                if turn.expected_kinds == ["answered"] and not turn.references:
                    raise ValueError(f"Answered case needs evidence: {case.id}")
        return self


def load_dataset(path: Path, source: Path) -> tuple[Dataset, dict]:
    dataset = Dataset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    if git(source, "rev-parse", "HEAD") != dataset.corpus_commit or git(
        source, "status", "--porcelain"
    ):
        raise ValueError("Evaluation source must be clean and match the dataset corpus commit.")
    anchors = {}
    policy_root = (source / "Policies").resolve()
    for key, ref in dataset.references.items():
        target = (source / ref.path).resolve()
        if not target.is_relative_to(policy_root) or target.suffix != ".md":
            raise ValueError(f"Invalid reference path: {ref.path}")
        content = target.read_text(encoding="utf-8")
        offset = content.find(ref.contains)
        if offset < 0:
            raise ValueError(f"Reference text missing from corpus: {key}")
        start = content[:offset].count("\n") + 1
        end = start + ref.contains.count("\n")
        anchors[key] = {**ref.model_dump(), "start_line": start, "end_line": end}
    return dataset, anchors


def structural_checks(response: dict, turn: EvalTurn, anchors: dict, database: Path, commit: str):
    citations = response.get("citations", [])
    with connect(database) as db:
        known = {row["chunk_id"]: dict(row) for row in db.execute("SELECT * FROM chunks")}
    valid = True
    for citation in citations:
        row = known.get(citation.get("chunk_id"))
        if not row or any(
            citation.get(key) != row[key]
            for key in ("path", "content", "source_url", "start_line", "end_line", "commit_sha")
        ):
            valid = False
    labels = [c.get("label") for c in citations]
    markers = [int(value) for value in re.findall(r"\[(\d+)\]", response.get("answer", ""))]
    valid = valid and labels == list(range(1, len(citations) + 1)) and set(markers) == set(labels)
    expected_paths = {anchors[key]["path"] for key in turn.references}
    cited_paths = {c.get("path") for c in citations}
    expected_anchors = [anchors[key] for key in turn.references]
    covered = [
        any(
            c.get("path") == anchor["path"]
            and c.get("start_line", 0) <= anchor["start_line"]
            and c.get("end_line", 0) >= anchor["end_line"]
            for c in citations
        )
        for anchor in expected_anchors
    ]
    return {
        "expected_kind": response.get("kind") in turn.expected_kinds,
        "citation_provenance": bool(valid),
        "policy_answer_has_citations": response.get("kind") != "answered" or bool(citations),
        "corpus_version": response.get("corpus_commit") == commit,
        "expected_document_coverage": len(expected_paths & cited_paths) / len(expected_paths)
        if expected_paths
        else None,
        "reference_anchor_coverage": sum(covered) / len(covered) if covered else None,
    }


def evaluate(dataset: Dataset, anchors: dict, service: ChatService, limit: int | None = None):
    results = []
    for case in dataset.cases[:limit]:
        history = []
        turns = []
        for index, turn in enumerate(case.turns):
            item = {
                "turn": index + 1,
                "question": turn.question,
                "expected": turn.model_dump(exclude={"question"}),
                "human_review": {
                    "correctness": None,
                    "grounding": None,
                    "citation_support": None,
                    "notes": "",
                },
            }
            try:
                response = service.chat(turn.question, history, include_trace=True)
                item["trace"] = response.pop("trace", [])
                item["response"] = response
                item["checks"] = structural_checks(
                    response, turn, anchors, service.settings.database, dataset.corpus_commit
                )
                history.append(HistoryTurn(question=turn.question, answer=response["answer"]))
            except Exception as exc:
                item["error_type"] = type(exc).__name__
                turns.append(item)
                break  # Follow-ups cannot be interpreted after a failed setup turn.
            turns.append(item)
        results.append(
            {
                "id": case.id,
                "category": case.category,
                "turns": turns,
                "expected_turns": len(case.turns),
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--validate",
        action="store_true",
        help="Validate cases and source anchors without API calls (default)",
    )
    mode.add_argument(
        "--live", action="store_true", help="Run real model requests; incurs provider charges"
    )
    parser.add_argument("--dataset", type=Path, default=Path("evals/datasets/answers.yaml"))
    parser.add_argument("--output", type=Path, default=Path("evals/reports/answers-live.json"))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    settings = Settings()
    dataset, anchors = load_dataset(args.dataset, settings.data_dir / "source" / "site-policy")
    if not args.live:
        print(
            json.dumps(
                {
                    "validated_cases": len(dataset.cases),
                    "validated_turns": sum(len(c.turns) for c in dataset.cases),
                    "source_anchors": len(anchors),
                    "live_model": False,
                }
            )
        )
        return
    create_chat(settings)  # Fail fast on missing provider configuration; no generation request.
    status = corpus_status(settings.database)
    if status["commit"] != dataset.corpus_commit:
        parser.error("Indexed corpus does not match the dataset; sync and index the pinned source.")
    # Freeze evaluation evidence in a temporary corpus copy; context remains in memory.
    with tempfile.TemporaryDirectory(prefix="policy-eval-", dir=settings.data_dir) as temp:
        evaluation_settings = settings.model_copy(update={"data_dir": Path(temp)})
        with (
            closing(sqlite3.connect(settings.database)) as source,
            closing(sqlite3.connect(evaluation_settings.database)) as target,
        ):
            source.backup(target)
        results = evaluate(dataset, anchors, ChatService(evaluation_settings), args.limit)
    turns = [turn for case in results for turn in case["turns"]]
    completed = [turn for turn in turns if "checks" in turn]
    check_names = (
        "expected_kind",
        "citation_provenance",
        "policy_answer_has_citations",
        "corpus_version",
    )
    rates = {
        name: sum(bool(turn["checks"][name]) for turn in completed) / len(completed)
        if completed
        else None
        for name in check_names
    }
    report = {
        "evaluation": "agent-structure-with-human-review",
        "live_model": True,
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset_version": dataset.version,
        "corpus": status,
        "chat_provider": settings.chat_provider,
        "chat_model": settings.chat_model,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "retrieval_mode": settings.retrieval_mode,
        "conversation_mode": "caller-owned-memory",
        "cases": results,
        "summary": {
            "cases": len(results),
            "completed_turns": len(completed),
            "expected_turns": sum(c["expected_turns"] for c in results),
            "errors": sum("error_type" in turn for turn in turns),
            "structural_pass_rates": rates,
            "semantic_quality": "pending human review",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report["summary"]))


if __name__ == "__main__":
    main()
