from pathlib import Path

import pytest
import yaml
from policy_agent.config import Settings
from policy_agent.conversations import ConversationService
from policy_agent.ingestion import git

from evals.answers import Dataset, evaluate, load_dataset, structural_checks
from tests.fakes import ScriptedModel, call, cited_answer


def fixture_dataset(corpus, tmp_path):
    repo, _, _ = corpus
    value = {
        "version": 1,
        "corpus_commit": git(repo, "rev-parse", "HEAD"),
        "references": {
            "appeal": {
                "path": "Policies/appeals.md",
                "contains": "Users can appeal an account suspension",
            }
        },
        "cases": [
            {
                "id": "appeal",
                "category": "factual",
                "turns": [
                    {
                        "question": "Can I appeal?",
                        "expected_kinds": ["answered"],
                        "references": ["appeal"],
                        "facts": ["Use the form."],
                    }
                ],
            }
        ],
    }
    path = tmp_path / "dataset.yaml"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    return path


def test_source_anchored_dataset_and_scripted_execution(corpus, tmp_path):
    path = fixture_dataset(corpus, tmp_path)
    dataset, anchors = load_dataset(path, corpus[0])
    assert anchors["appeal"]["start_line"] == 6
    model = ScriptedModel(call("search_policies", query="appeals"), cited_answer)
    service = ConversationService(Settings(data_dir=corpus[1].parent), lambda _: model)
    existing = service.create()["id"]
    report = evaluate(dataset, anchors, service)
    turn = report[0]["turns"][0]
    assert turn["checks"]["citation_provenance"]
    assert turn["checks"]["reference_anchor_coverage"] == 1
    assert turn["human_review"]["correctness"] is None
    assert [row["id"] for row in service.list()] == [existing]


def test_eval_failure_skips_dependent_followups_and_cleans_up(corpus, tmp_path):
    dataset, anchors = load_dataset(fixture_dataset(corpus, tmp_path), corpus[0])
    dataset.cases[0].turns.append(dataset.cases[0].turns[0].model_copy())
    model = ScriptedModel(RuntimeError("test transport error"))
    service = ConversationService(Settings(data_dir=corpus[1].parent), lambda _: model)
    results = evaluate(dataset, anchors, service)
    assert results[0]["expected_turns"] == 2
    assert len(results[0]["turns"]) == 1
    assert results[0]["turns"][0]["error_type"] == "RuntimeError"
    assert service.list() == []


def test_corrupted_citation_does_not_pass_provenance(corpus, tmp_path):
    dataset, anchors = load_dataset(fixture_dataset(corpus, tmp_path), corpus[0])
    response = {
        "kind": "answered",
        "answer": "Wrong [1]",
        "corpus_commit": dataset.corpus_commit,
        "citations": [{"label": 1, "chunk_id": "made-up", "content": "fake"}],
    }
    result = structural_checks(
        response, dataset.cases[0].turns[0], anchors, corpus[1], dataset.corpus_commit
    )
    assert not result["citation_provenance"]


def test_changed_source_anchor_is_rejected(corpus, tmp_path):
    path = fixture_dataset(corpus, tmp_path)
    value = yaml.safe_load(path.read_text())
    value["references"]["appeal"]["contains"] = "This text was never in the policy."
    path.write_text(yaml.safe_dump(value))
    with pytest.raises(ValueError, match="Reference text missing"):
        load_dataset(path, corpus[0])


def test_eval_cases_schema_has_required_coverage():
    path = Path(__file__).resolve().parents[1] / "evals/datasets/answers.yaml"
    dataset = Dataset.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert 40 <= len(dataset.cases) <= 60
    assert {case.category for case in dataset.cases} == {
        "factual",
        "multi_turn",
        "cross_document",
        "false_premise",
        "insufficient",
        "out_of_scope",
        "injection",
        "multilingual",
    }
