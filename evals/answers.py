"""Source-anchored cases; structural metrics and human quality review stay separate."""

import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import yaml
from policy_agent.chat import ChatService, HistoryTurn
from policy_agent.config import Settings
from policy_agent.github_source import REPOSITORY_URL, PolicyRepository
from policy_agent.providers import create_chat
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
    corpus_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
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


def load_dataset(path: Path, repository: PolicyRepository) -> tuple[Dataset, dict, dict]:
    dataset = Dataset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    directory = repository.list_documents()
    if directory["commit"] != dataset.corpus_commit:
        raise ValueError("Evaluation source must match the dataset's immutable policy commit.")
    anchors, documents = {}, {}
    for key, ref in dataset.references.items():
        if ref.path not in documents:
            repository.read_document(ref.path)
            documents[ref.path] = "\n".join(repository.files[ref.path])
        content = documents[ref.path]
        offset = content.find(ref.contains)
        if offset < 0:
            raise ValueError(f"Reference text missing from GitHub snapshot: {key}")
        start = content[:offset].count("\n") + 1
        end = start + ref.contains.count("\n")
        anchors[key] = {**ref.model_dump(), "start_line": start, "end_line": end}
    return dataset, anchors, documents


def structural_checks(
    response: dict,
    turn: EvalTurn,
    anchors: dict,
    documents: dict[str, str],
    commit: str,
    trace: list[dict],
):
    citations = response.get("citations", [])
    reads = [item for item in trace if item.get("event") == "read"]
    valid = True
    for citation in citations:
        path, start, end = (citation.get(k) for k in ("path", "start_line", "end_line"))
        content = documents.get(path)
        if content is None:
            valid = False
            continue
        lines = content.splitlines()
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not 1 <= start <= end <= len(lines)
        ):
            valid = False
            continue
        url = f"{REPOSITORY_URL}/blob/{commit}/{quote(path, safe='/')}#L{start}-L{end}"
        read_matches = any(
            item.get("path") == path
            and item["start_line"] <= start <= end <= item["end_line"]
            and item["source_id"] == citation.get("source_id")
            and item["source_id"]
            == hashlib.sha256(
                f"{commit}:{path}:{item['start_line']}:{item['end_line']}".encode()
            ).hexdigest()[:20]
            for item in reads
        )
        valid = valid and read_matches and citation.get("commit_sha") == commit
        valid = valid and citation.get("source_url") == url
        valid = valid and citation.get("content") == "\n".join(lines[start - 1 : end])
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
        "source_version": response.get("source_commit") in (commit, None)
        and (not citations or response.get("source_commit") == commit),
        "expected_document_coverage": len(expected_paths & cited_paths) / len(expected_paths)
        if expected_paths
        else None,
        "reference_anchor_coverage": sum(covered) / len(covered) if covered else None,
    }


def evaluate(
    dataset: Dataset,
    anchors: dict,
    service: ChatService,
    documents: dict[str, str],
    limit: int | None = None,
    *,
    source_repository: PolicyRepository | None = None,
    workers: int = 1,
):
    if workers > 1:

        def run_case(case):
            subset = dataset.model_copy(update={"cases": [case]})
            with service.repository_factory(service.settings) as validator:
                validator.list_documents()
                return evaluate(
                    subset, anchors, service, dict(documents), source_repository=validator
                )[0]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(run_case, dataset.cases[:limit]))
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
                response = service.chat(turn.question, history[-20:], include_trace=True)
                item["trace"] = response.pop("trace", [])
                item["response"] = response
                # A valid answer may cite a different supporting policy than a gold anchor.
                # Verify that original independently, without giving oracle text to the agent.
                if source_repository is not None:
                    for citation in response.get("citations", []):
                        path = citation["path"]
                        if path not in documents:
                            source_repository.read_document(path)
                            documents[path] = "\n".join(source_repository.files[path])
                item["checks"] = structural_checks(
                    response, turn, anchors, documents, dataset.corpus_commit, item["trace"]
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
        help="Read GitHub to validate cases and source anchors; no model calls (default)",
    )
    mode.add_argument(
        "--live", action="store_true", help="Run real model requests; incurs provider charges"
    )
    parser.add_argument("--dataset", type=Path, default=Path("evals/datasets/answers.yaml"))
    parser.add_argument("--output", type=Path, default=Path("evals/reports/answers-local.json"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 5))
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    dataset_config = Dataset.model_validate(
        yaml.safe_load(args.dataset.read_text(encoding="utf-8"))
    )
    settings = Settings(github_ref=dataset_config.corpus_commit)
    # Expected-source text is held in evaluator memory, never supplied to the agent.
    with PolicyRepository(settings) as repository:
        dataset, anchors, documents = load_dataset(args.dataset, repository)
        if not args.live:
            print(
                json.dumps(
                    {
                        "validated_cases": len(dataset.cases),
                        "validated_turns": sum(len(c.turns) for c in dataset.cases),
                        "source_anchors": len(anchors),
                        "live_model": False,
                        "source_mode": "github-online",
                    }
                )
            )
            return
        create_chat(settings)  # Configuration check only; no generation.
        results = evaluate(
            dataset,
            anchors,
            ChatService(settings),
            documents,
            args.limit,
            source_repository=repository,
            workers=args.workers,
        )
    turns = [turn for case in results for turn in case["turns"]]
    completed = [turn for turn in turns if "checks" in turn]
    check_names = (
        "expected_kind",
        "citation_provenance",
        "policy_answer_has_citations",
        "source_version",
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
        "policy_source": {"repository": REPOSITORY_URL, "commit": dataset.corpus_commit},
        "chat_provider": settings.chat_provider,
        "chat_model": settings.chat_model,
        "source_mode": "github-online",
        "workers": args.workers,
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
