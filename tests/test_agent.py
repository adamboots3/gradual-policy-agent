from concurrent.futures import ThreadPoolExecutor

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from policy_agent.agent import validate_answer
from policy_agent.chat import ChatService, HistoryTurn
from policy_agent.config import Settings
from policy_agent.providers import ConfigurationError

from tests.fakes import ScriptedModel, call, cited_answer


def service_for(corpus, *models):
    models = iter(models)
    return ChatService(Settings(data_dir=corpus[1].parent), lambda _: next(models))


def answering_model():
    return ScriptedModel(call("search_policies", query="appeal suspension"), cited_answer)


def test_followup_uses_only_explicit_context_and_never_stores_dialogue(corpus):
    first, second, fresh = answering_model(), answering_model(), answering_model()
    service = service_for(corpus, first, second, fresh)
    response = service.chat("Can I appeal?")
    assert response["kind"] == "answered" and "[1]" in response["answer"]
    assert response["citations"][0]["source_url"].startswith("https://github.com/")
    assert "trace" not in response
    history = [HistoryTurn(question="Can I appeal?", answer=response["answer"])]
    service.chat("What about the deadline?", history)
    assert [m.content for m in second.inputs[0] if isinstance(m, HumanMessage)] == [
        "Can I appeal?",
        "What about the deadline?",
    ]
    assert len(history) == 1  # The service cannot mutate the caller's context.
    service.chat("A new window")
    assert [m.content for m in fresh.inputs[0] if isinstance(m, HumanMessage)] == ["A new window"]
    assert not any(isinstance(m, AIMessage) for m in fresh.inputs[0])
    assert {p.name for p in corpus[1].parent.glob("*.sqlite3*")} == {"policies.sqlite3"}


def test_server_restart_has_no_history_to_restore(corpus):
    service_for(corpus, answering_model()).chat("Context from an old process")
    model = answering_model()
    service_for(corpus, model).chat("New process")
    assert "Context from an old process" not in str(model.inputs[0])


def test_all_twenty_frontend_turns_are_used_and_legacy_databases_are_not_read(corpus, monkeypatch):
    legacy = corpus[1].parent / "conversations.sqlite3"
    legacy.write_bytes(b"Old dialogue storage must never be opened")
    model = answering_model()
    monkeypatch.setenv("POLICY_HISTORY_TURNS", "6")  # Obsolete setting has no effect.
    service = service_for(corpus, model)
    history = [HistoryTurn(question=f"Question {i}", answer=f"Answer {i}") for i in range(20)]
    service.chat("Now?", history)
    assert [m.content for m in model.inputs[0] if isinstance(m, HumanMessage)] == [
        *[turn.question for turn in history],
        "Now?",
    ]
    assert [m.content for m in model.inputs[0] if isinstance(m, AIMessage)] == [
        turn.answer for turn in history
    ]
    assert legacy.read_bytes() == b"Old dialogue storage must never be opened"


def test_unknown_citation_rejected_then_repaired(corpus):
    model = ScriptedModel(
        call("search_policies", query="appeals"),
        call("submit_answer", kind="answered", answer="Claim [[invented]]"),
        cited_answer,
    )
    result = service_for(corpus, model).chat("Can I appeal?", include_trace=True)
    assert result["kind"] == "answered" and "invented" not in result["answer"]
    assert any(item["event"] == "validation_error" for item in result["trace"])


def test_policy_answer_without_search_is_not_accepted(corpus):
    model = ScriptedModel(*[call("submit_answer", kind="answered", answer="Trust me.")] * 6)
    result = service_for(corpus, model).chat("What is the policy?")
    assert result["kind"] == "insufficient_evidence" and result["citations"] == []


def test_previous_turn_evidence_cannot_be_reused_without_search(corpus):
    previous = service_for(corpus, answering_model()).chat("Can I appeal?")
    marker = previous["citations"][0]["chunk_id"]
    model = ScriptedModel(
        *[call("submit_answer", kind="answered", answer=f"Same [[{marker}]]")] * 6
    )
    result = service_for(corpus, model).chat(
        "And now?", [HistoryTurn(question="Can I appeal?", answer=previous["answer"])]
    )
    assert result["kind"] == "insufficient_evidence" and not result["citations"]
    assert result["search_calls"] == 0


def test_search_budget_enforced(corpus):
    model = ScriptedModel(*[call("search_policies", query="appeals")] * 6)
    result = service_for(corpus, model).chat("What is the policy?")
    assert result["search_calls"] == 3 and len(model.inputs) == 6
    assert result["kind"] == "insufficient_evidence"


def test_greeting_can_bypass_search(corpus):
    model = ScriptedModel(call("submit_answer", kind="greeting", answer="Hello!"))
    result = service_for(corpus, model).chat("Hello")
    assert result["search_calls"] == 0 and result["citations"] == []


def test_refusal_cannot_claim_the_full_policy_has_no_rule(corpus):
    model = ScriptedModel(
        call(
            "submit_answer",
            kind="insufficient_evidence",
            answer="The full policy has no deadline whatsoever.",
        )
    )
    result = service_for(corpus, model).chat("What is the deadline?")
    assert "no deadline" not in result["answer"]
    assert "enough available evidence" in result["answer"]


def test_failed_turn_leaves_no_state_for_retry(corpus):
    bad = ScriptedModel(call("search_policies", query="appeals"), RuntimeError("provider down"))
    good = answering_model()
    service = service_for(corpus, bad, good)
    with pytest.raises(RuntimeError):
        service.chat("Failed question")
    service.chat("Retry question")
    assert [m.content for m in good.inputs[0] if isinstance(m, HumanMessage)] == ["Retry question"]
    assert not any(isinstance(m, AIMessage) for m in good.inputs[0])
    assert not (corpus[1].parent / "checkpoints.sqlite3").exists()
    assert not (corpus[1].parent / "conversations.sqlite3").exists()


def test_concurrent_windows_cannot_share_context(corpus):
    models = []

    def factory(_):
        model = answering_model()
        models.append(model)
        return model

    service = ChatService(Settings(data_dir=corpus[1].parent), factory)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.chat, ["Private window A", "Independent window B"]))
    assert all(result["kind"] == "answered" for result in results)
    assert sorted(
        [m.content for m in model.inputs[0] if isinstance(m, HumanMessage)] for model in models
    ) == [["Independent window B"], ["Private window A"]]


def test_missing_provider_creates_no_history(corpus):
    service = ChatService(Settings(data_dir=corpus[1].parent))
    with pytest.raises(ConfigurationError, match="CHAT_PROVIDER"):
        service.chat("Question")
    assert not (corpus[1].parent / "conversations.sqlite3").exists()


@pytest.mark.parametrize(
    "answer", ["Bad [[unknown]]", "Link https://example.com", "Broken [[id", "Fake [99]"]
)
def test_citation_gate_rejects_bad_answers(answer):
    with pytest.raises(ValueError):
        validate_answer({"kind": "answered", "answer": answer}, {}, 1)
