import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from policy_agent.agent import validate_answer
from policy_agent.config import Settings
from policy_agent.conversations import ConversationNotFound, ConversationService
from policy_agent.providers import ConfigurationError

from tests.fakes import ScriptedModel, call, cited_answer


def service_for(corpus, *models):
    models = iter(models)
    return ConversationService(Settings(data_dir=corpus[1].parent), lambda _: next(models))


def answering_model():
    return ScriptedModel(call("search_policies", query="appeal suspension"), cited_answer)


def test_persisted_history_and_current_turn_citations(corpus):
    first, second = answering_model(), answering_model()
    service = service_for(corpus, first)
    conversation = service.create()["id"]
    response = service.chat(conversation, "Can I appeal?")
    assert response["kind"] == "answered"
    assert response["search_calls"] == 1
    assert "[1]" in response["answer"]
    assert response["citations"][0]["source_url"].startswith("https://github.com/")
    # A new service instance simulates process restart, not in-memory history.
    restarted = service_for(corpus, second)
    restarted.chat(conversation, "What about the deadline?")
    humans = [m.content for m in second.inputs[0] if isinstance(m, HumanMessage)]
    assert humans == ["Can I appeal?", "What about the deadline?"]
    assert len(restarted.get(conversation)["turns"]) == 2


def test_unknown_citation_rejected_then_repaired(corpus):
    model = ScriptedModel(
        call("search_policies", query="appeals"),
        call("submit_answer", kind="answered", answer="Claim [[invented]]"),
        cited_answer,
    )
    service = service_for(corpus, model)
    result = service.chat(service.create()["id"], "Can I appeal?")
    assert result["kind"] == "answered"
    assert "invented" not in result["answer"]
    with service.connect() as db:
        metadata = json.loads(db.execute("SELECT metadata FROM runs").fetchone()[0])
    assert any(item["event"] == "validation_error" for item in metadata["trace"])


def test_policy_answer_without_search_is_not_accepted(corpus):
    model = ScriptedModel(*[call("submit_answer", kind="answered", answer="Trust me.")] * 6)
    service = service_for(corpus, model)
    result = service.chat(service.create()["id"], "What is the policy?")
    assert result["kind"] == "insufficient_evidence"
    assert result["citations"] == []


def test_previous_turn_evidence_cannot_be_reused_without_search(corpus):
    first = answering_model()
    service = service_for(corpus, first)
    conversation = service.create()["id"]
    previous = service.chat(conversation, "Can I appeal?")
    marker = previous["citations"][0]["chunk_id"]
    ungrounded = ScriptedModel(
        *[call("submit_answer", kind="answered", answer=f"Same claim [[{marker}]]")] * 6
    )
    restarted = service_for(corpus, ungrounded)
    result = restarted.chat(conversation, "And now?")
    assert result["kind"] == "insufficient_evidence"
    assert result["search_calls"] == 0
    assert not result["citations"]


def test_search_budget_enforced(corpus):
    model = ScriptedModel(*[call("search_policies", query="appeals")] * 6)
    service = service_for(corpus, model)
    result = service.chat(service.create()["id"], "What is the policy?")
    assert result["search_calls"] == 3
    assert len(model.inputs) == 6
    assert result["kind"] == "insufficient_evidence"


def test_greeting_can_bypass_search(corpus):
    service = service_for(
        corpus, ScriptedModel(call("submit_answer", kind="greeting", answer="Hello!"))
    )
    result = service.chat(service.create()["id"], "Hello")
    assert result["search_calls"] == 0
    assert result["citations"] == []


def test_refusal_cannot_claim_the_full_policy_has_no_rule(corpus):
    model = ScriptedModel(
        call(
            "submit_answer",
            kind="insufficient_evidence",
            answer="The full policy has no deadline whatsoever.",
        )
    )
    service = service_for(corpus, model)
    result = service.chat(service.create()["id"], "What is the deadline?")
    assert "no deadline" not in result["answer"]
    assert "enough available evidence" in result["answer"]


def test_failed_turn_is_not_replayed_on_retry(corpus):
    bad = ScriptedModel(call("search_policies", query="appeals"), RuntimeError("provider down"))
    good = answering_model()
    service = service_for(corpus, bad, good)
    conversation = service.create()["id"]
    with pytest.raises(RuntimeError):
        service.chat(conversation, "Failed question")
    assert service.get(conversation)["turns"] == []
    service.chat(conversation, "Retry question")
    assert [m.content for m in good.inputs[0] if isinstance(m, HumanMessage)] == ["Retry question"]
    assert not any(isinstance(m, AIMessage) for m in good.inputs[0])
    with service.connect() as db:
        assert [row[0] for row in db.execute("SELECT status FROM runs ORDER BY rowid")] == [
            "failed",
            "completed",
        ]


def test_conversations_are_isolated_and_delete_removes_checkpoints(corpus):
    first, second = answering_model(), answering_model()
    service = service_for(corpus, first, second)
    a, b = service.create()["id"], service.create()["id"]
    service.chat(a, "Private context A")
    service.chat(b, "Independent B")
    assert "Private context A" not in str(second.inputs[0])
    service.delete(a)
    with pytest.raises(ConversationNotFound):
        service.get(a)
    with SqliteSaver.from_conn_string(
        str(service.settings.data_dir / "checkpoints.sqlite3")
    ) as saver:
        assert saver.get_tuple({"configurable": {"thread_id": a}}) is None
    with service.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM runs WHERE conversation_id=?", (a,)).fetchone()[0] == 0
        )
    assert len(service.get(b)["turns"]) == 1


def test_same_conversation_requests_are_serialized(corpus):
    first, second = answering_model(), answering_model()
    service = service_for(corpus, first, second)
    conversation = service.create()["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda q: service.chat(conversation, q), ["Question A", "Question B"])
        )
    assert all(row["kind"] == "answered" for row in results)
    assert len([m for m in second.inputs[0] if isinstance(m, HumanMessage)]) == 2


def test_missing_provider_fails_without_recording_partial_turn(corpus):
    service = ConversationService(Settings(data_dir=corpus[1].parent))
    conversation = service.create()["id"]
    with pytest.raises(ConfigurationError, match="CHAT_PROVIDER"):
        service.chat(conversation, "Question")
    assert service.get(conversation)["turns"] == []


@pytest.mark.parametrize(
    "answer", ["Bad [[unknown]]", "Link https://example.com", "Broken [[id", "Fake [99]"]
)
def test_citation_gate_rejects_bad_answers(answer):
    with pytest.raises(ValueError):
        validate_answer({"kind": "answered", "answer": answer}, {}, 1)
