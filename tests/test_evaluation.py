from pathlib import Path

import pytest
import yaml
from langchain_core.messages import HumanMessage
from policy_agent.chat import ChatService
from policy_agent.config import Settings

from evals.answers import Dataset, evaluate, load_dataset, structural_checks
from tests.fakes import ScriptedModel, answering_model, call, cited_answer


def fixture_dataset(corpus, tmp_path):
    value = {
        "version": 1,
        "corpus_commit": corpus.commit,
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
    with corpus.factory(Settings()) as repository:
        dataset, anchors, documents = load_dataset(path, repository)
    assert anchors["appeal"]["start_line"] == 3
    model = answering_model()
    service = ChatService(Settings(), lambda _: model, corpus.factory)
    report = evaluate(dataset, anchors, service, documents)
    turn = report[0]["turns"][0]
    assert turn["checks"]["citation_provenance"]
    assert turn["checks"]["reference_anchor_coverage"] == 1
    assert turn["human_review"]["correctness"] is None
    assert turn["trace"]


def test_eval_failure_skips_dependent_followups_and_cleans_up(corpus, tmp_path):
    with corpus.factory(Settings()) as repository:
        dataset, anchors, documents = load_dataset(fixture_dataset(corpus, tmp_path), repository)
    dataset.cases[0].turns.append(dataset.cases[0].turns[0].model_copy())
    model = ScriptedModel(RuntimeError("test transport error"))
    service = ChatService(Settings(), lambda _: model, corpus.factory)
    results = evaluate(dataset, anchors, service, documents)
    assert results[0]["expected_turns"] == 2
    assert len(results[0]["turns"]) == 1
    assert results[0]["turns"][0]["error_type"] == "RuntimeError"


def test_eval_context_is_temporary_and_resets_between_scenarios(corpus, tmp_path):
    with corpus.factory(Settings()) as repository:
        dataset, anchors, documents = load_dataset(fixture_dataset(corpus, tmp_path), repository)
    independent = dataset.cases[0].model_copy(deep=True, update={"id": "independent"})
    dataset.cases[0].turns.append(dataset.cases[0].turns[0].model_copy())
    dataset.cases.append(independent)
    models = [answering_model() for _ in range(3)]
    remaining = iter(models)
    service = ChatService(Settings(), lambda _: next(remaining), corpus.factory)
    results = evaluate(dataset, anchors, service, documents)
    assert len(results[0]["turns"]) == 2 and len(results[1]["turns"]) == 1
    assert len([m for m in models[1].inputs[0] if isinstance(m, HumanMessage)]) == 2
    assert len([m for m in models[2].inputs[0] if isinstance(m, HumanMessage)]) == 1


def test_parallel_evaluation_keeps_scenarios_independent(corpus, tmp_path):
    with corpus.factory(Settings()) as repository:
        dataset, anchors, documents = load_dataset(fixture_dataset(corpus, tmp_path), repository)
    dataset.cases.append(dataset.cases[0].model_copy(deep=True, update={"id": "independent"}))
    service = ChatService(Settings(), lambda _: answering_model(), corpus.factory)
    reports = evaluate(dataset, anchors, service, documents, workers=2)
    assert [report["id"] for report in reports] == ["appeal", "independent"]
    assert all(report["turns"][0]["checks"]["citation_provenance"] for report in reports)


def test_corrupted_citation_does_not_pass_provenance(corpus, tmp_path):
    with corpus.factory(Settings()) as repository:
        dataset, anchors, documents = load_dataset(fixture_dataset(corpus, tmp_path), repository)
    response = {
        "kind": "answered",
        "answer": "Wrong [1]",
        "source_commit": dataset.corpus_commit,
        "citations": [{"label": 1, "source_id": "made-up", "content": "fake"}],
    }
    result = structural_checks(
        response, dataset.cases[0].turns[0], anchors, documents, dataset.corpus_commit, []
    )
    assert not result["citation_provenance"]


def test_alternative_supporting_file_is_verified_without_gold_path_assumption(corpus, tmp_path):
    corpus.files["Policies/alternative.md"] = corpus.files["Policies/appeals.md"]
    with corpus.factory(Settings()) as repository:
        dataset, anchors, documents = load_dataset(fixture_dataset(corpus, tmp_path), repository)
        model = ScriptedModel(
            call("list_policy_documents"),
            call("read_policy_document", path="Policies/alternative.md"),
            cited_answer,
        )
        service = ChatService(Settings(), lambda _: model, corpus.factory)
        report = evaluate(dataset, anchors, service, documents, source_repository=repository)
    checks = report[0]["turns"][0]["checks"]
    assert checks["citation_provenance"] is True
    assert checks["expected_document_coverage"] == 0


def test_changed_source_anchor_is_rejected(corpus, tmp_path):
    path = fixture_dataset(corpus, tmp_path)
    value = yaml.safe_load(path.read_text())
    value["references"]["appeal"]["contains"] = "This text was never in the policy."
    path.write_text(yaml.safe_dump(value))
    with corpus.factory(Settings()) as repository:
        with pytest.raises(ValueError, match="Reference text missing"):
            load_dataset(path, repository)


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
