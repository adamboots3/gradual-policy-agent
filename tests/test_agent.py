from concurrent.futures import ThreadPoolExecutor

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from policy_agent.agent import validate_answer
from policy_agent.chat import ChatService, HistoryTurn
from policy_agent.config import Settings
from policy_agent.github_source import PolicySourceError
from policy_agent.providers import ConfigurationError

from tests.fakes import ScriptedModel, answering_model, call, cited_answer


def service_for(corpus, *models):
    models = iter(models)
    return ChatService(Settings(), lambda _: next(models), corpus.factory)


def test_followup_uses_only_explicit_context_and_never_stores_dialogue(
    corpus, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    first, second, fresh = answering_model(), answering_model(), answering_model()
    service = service_for(corpus, first, second, fresh)
    response = service.chat("Can I appeal?")
    assert response["kind"] == "answered" and "[1]" in response["answer"]
    assert response["citations"][0]["source_url"].startswith("https://github.com/")
    assert response["source_commit"] == corpus.commit and "trace" not in response
    history = [HistoryTurn(question="Can I appeal?", answer=response["answer"])]
    service.chat("What about the deadline?", history)
    assert [m.content for m in second.inputs[0] if isinstance(m, HumanMessage)] == [
        "Can I appeal?",
        "What about the deadline?",
    ]
    assert len(history) == 1
    service.chat("A new window")
    assert [m.content for m in fresh.inputs[0] if isinstance(m, HumanMessage)] == ["A new window"]
    assert not any(isinstance(m, AIMessage) for m in fresh.inputs[0])
    assert not list(tmp_path.iterdir())


def test_all_twenty_frontend_turns_are_used_and_legacy_files_are_not_read(
    corpus, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "policies.sqlite3"
    legacy.write_bytes(b"Legacy storage must never be opened")
    monkeypatch.setenv("POLICY_HISTORY_TURNS", "6")
    monkeypatch.setenv("POLICY_RETRIEVAL_MODE", "hybrid")
    model = answering_model()
    history = [HistoryTurn(question=f"Q{i}", answer=f"A{i}") for i in range(20)]
    service_for(corpus, model).chat("Now?", history)
    assert [m.content for m in model.inputs[0] if isinstance(m, HumanMessage)] == [
        *[t.question for t in history],
        "Now?",
    ]
    assert [m.content for m in model.inputs[0] if isinstance(m, AIMessage)] == [
        t.answer for t in history
    ]
    assert legacy.read_bytes() == b"Legacy storage must never be opened"


def test_unknown_or_out_of_range_citation_rejected_then_repaired(corpus):
    def invalid(messages):
        response = cited_answer(messages)
        response.tool_calls[0]["args"]["citations"][0]["end_line"] = 10000
        return response

    model = ScriptedModel(
        call("list_policy_documents"),
        call("read_policy_document", path="Policies/appeals.md"),
        invalid,
        cited_answer,
    )
    result = service_for(corpus, model).chat("Can I appeal?", include_trace=True)
    assert result["kind"] == "answered"
    assert any(item["event"] == "validation_error" for item in result["trace"])


def test_multiple_exact_passages_from_same_read_have_independent_labels(corpus):
    with corpus.factory(Settings()) as repository:
        repository.list_documents()
        row = repository.read_document("Policies/appeals.md")
    response = validate_answer(
        {
            "kind": "answered",
            "answer": "Use the form [[1]]. Six months [[2]].",
            "citations": [
                {"source_id": row["source_id"], "start_line": 3, "end_line": 3},
                {"source_id": row["source_id"], "start_line": 7, "end_line": 7},
            ],
        },
        {row["source_id"]: row},
        1,
    )
    assert response["answer"] == "Use the form [1]. Six months [2]."
    assert [c["label"] for c in response["citations"]] == [1, 2]
    assert "reinstatement form" in response["citations"][0]["content"]
    assert "six months" in response["citations"][1]["content"]
    assert response["citations"][0]["source_id"] == response["citations"][1]["source_id"]


def test_policy_answer_without_read_is_not_accepted(corpus):
    model = ScriptedModel(*[call("submit_answer", kind="answered", answer="Trust me.")] * 10)
    result = service_for(corpus, model).chat("What is the policy?")
    assert result["kind"] == "insufficient_evidence" and result["citations"] == []


def test_previous_turn_evidence_cannot_be_reused_without_reading(corpus):
    previous = service_for(corpus, answering_model()).chat("Can I appeal?")
    ref = previous["citations"][0]
    model = ScriptedModel(
        *[
            call(
                "submit_answer",
                kind="answered",
                answer="Same [[1]]",
                citations=[{k: ref[k] for k in ("source_id", "start_line", "end_line")}],
            )
        ]
        * 10
    )
    result = service_for(corpus, model).chat(
        "And now?", [HistoryTurn(question="Can I appeal?", answer=previous["answer"])]
    )
    assert result["kind"] == "insufficient_evidence" and not result["citations"]
    assert result["read_calls"] == 0


def test_read_budget_and_model_budget_are_enforced(corpus):
    model = ScriptedModel(
        call("list_policy_documents"),
        *[call("read_policy_document", path="Policies/appeals.md")] * 9,
    )
    result = service_for(corpus, model).chat("What is the policy?")
    assert result["read_calls"] == 6 and len(model.inputs) == 10
    assert result["kind"] == "insufficient_evidence"
    assert len([r for r in corpus.calls if "/blobs/" in r.url.path]) == 1


def test_greeting_bypasses_github(corpus):
    result = service_for(
        corpus, ScriptedModel(call("submit_answer", kind="greeting", answer="Hello!"))
    ).chat("Hi")
    assert result["source_commit"] is None and result["read_calls"] == 0
    assert corpus.calls == []


def test_source_failure_aborts_instead_of_answering_from_memory(corpus):
    def broken(_):
        raise PolicySourceError("GitHub unavailable")

    service = service_for(corpus, ScriptedModel(call("list_policy_documents"), cited_answer))
    corpus.respond = broken
    with pytest.raises(PolicySourceError):
        service.chat("Can I appeal?")


def test_refusal_cannot_claim_full_policy_has_no_rule(corpus):
    model = ScriptedModel(
        call(
            "submit_answer",
            kind="insufficient_evidence",
            answer="The full policy has no deadline whatsoever.",
        )
    )
    result = service_for(corpus, model).chat("What is the deadline?")
    assert "no deadline" not in result["answer"]


def test_failed_turn_leaves_no_state_for_retry(corpus):
    bad = ScriptedModel(call("list_policy_documents"), RuntimeError("provider down"))
    good = answering_model()
    service = service_for(corpus, bad, good)
    with pytest.raises(RuntimeError):
        service.chat("Failed")
    service.chat("Retry")
    assert [m.content for m in good.inputs[0] if isinstance(m, HumanMessage)] == ["Retry"]
    assert len([r for r in corpus.calls if "/commits/" in r.url.path]) == 2


def test_concurrent_windows_do_not_share_context(corpus):
    models = []

    def factory(_):
        model = answering_model()
        models.append(model)
        return model

    service = ChatService(Settings(), factory, corpus.factory)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.chat, ["Window A", "Window B"]))
    assert all(r["kind"] == "answered" for r in results)
    assert sorted(
        [m.content for m in model.inputs[0] if isinstance(m, HumanMessage)] for model in models
    ) == [["Window A"], ["Window B"]]


def test_missing_provider_never_accesses_github(corpus):
    with pytest.raises(ConfigurationError, match="CHAT_PROVIDER"):
        ChatService(Settings(), repository_factory=corpus.factory).chat("Question")
    assert not corpus.calls


@pytest.mark.parametrize(
    "answer",
    [
        "Bad [[unknown]]",
        "Link https://example.com",
        "Broken [[id",
        "Fake [99]",
        "Use support.github.com/contact/reinstatement",
    ],
)
def test_citation_gate_rejects_bad_answers(answer):
    with pytest.raises(ValueError):
        validate_answer({"kind": "answered", "answer": answer}, {}, 1)
