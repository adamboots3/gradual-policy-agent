import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from policy_agent.api import create_app
from policy_agent.chat import ChatService, HistoryTurn
from policy_agent.config import Settings
from policy_agent.context import ContextBudget, ContextWindowError, is_context_overflow
from policy_agent.providers import ConfigurationError

from tests.fakes import ScriptedModel, call, cited_answer


class ProviderError(Exception):
    def __init__(self, message, status=400, code=None):
        super().__init__(message)
        self.status_code = status
        self.body = {"error": {"code": code}}


def greeting():
    return call("submit_answer", kind="greeting", answer="Hello!")


def test_budget_counts_tools_output_and_multilingual_text_and_drops_whole_turns():
    system = SystemMessage(content="System")
    messages = [
        HumanMessage(content="old" * 100),
        AIMessage(content="answer" * 100),
        HumanMessage(content="最近的问题"),
        AIMessage(content="最近的回答"),
        HumanMessage(content="当前问题"),
    ]
    tools = [{"name": "search", "parameters": {"query": "string"}}]
    counter = ContextBudget(10000, 100, 50)
    estimate = counter.estimate([system, *messages[2:]], tools)
    budget = ContextBudget(estimate + 150, 100, 50)
    kept, turns, actual = budget.fit(system, messages, 2, tools)
    assert kept == messages[2:] and turns == 1 and actual == estimate
    assert len(messages) == 5  # Caller state is unchanged.
    assert counter.estimate([system], tools) > counter.estimate([system], [])
    assert counter.estimate([HumanMessage(content="中文")], []) > counter.estimate(
        [HumanMessage(content="ab")], []
    )
    with pytest.raises(ContextWindowError):
        ContextBudget(estimate + 149, 100, 50).fit(system, messages[-1:], 0, tools * 100)


def test_profile_fallback_and_explicit_window():
    model = ScriptedModel()
    settings = Settings()
    assert ContextBudget.for_model(settings, model).window == 32768
    model.profile = {"max_input_tokens": 64000}
    assert ContextBudget.for_model(settings, model).window == 64000
    settings.chat_context_window_tokens = 16000
    assert ContextBudget.for_model(settings, model).window == 16000
    settings.chat_context_window_tokens = 100
    with pytest.raises(ConfigurationError, match="OUTPUT|output"):
        ContextBudget.for_model(settings, model)


def test_budget_is_rechecked_after_retrieval_without_breaking_tool_pairs(corpus):
    history = [HistoryTurn(question=f"Q{i}:" + "q" * 200, answer="a" * 200) for i in range(20)]
    settings = Settings(data_dir=corpus[1].parent)
    probe = ScriptedModel(call("search_policies", query="appeals"), cited_answer)
    service = ChatService(settings, lambda _: probe)
    rows = service.retriever.search("appeals")
    rows[0]["content"] = "Retrieved evidence " * 400

    class Retriever:
        def search(self, query):
            return rows

    service.retriever = Retriever()
    service.chat("Now?", history)
    budget = ContextBudget.for_model(settings, probe)
    # Allow all history at first, but only 18 turns once the large tool reply arrives.
    second_without_two_turns = [probe.inputs[1][0], *probe.inputs[1][5:]]
    settings.chat_context_window_tokens = (
        budget.estimate(second_without_two_turns, probe.tools) + budget.output + budget.margin
    )
    model = ScriptedModel(call("search_policies", query="appeals"), cited_answer)
    service.model_factory = lambda _: model
    response = service.chat("Now?", history, include_trace=True)
    assert len([m for m in model.inputs[0] if isinstance(m, HumanMessage)]) == 21
    second = model.inputs[1]
    assert second[1].content == history[2].question
    assert second[2].content == history[2].answer
    assert second[-3].content == "Now?"
    assert isinstance(second[-2], AIMessage) and isinstance(second[-1], ToolMessage)
    assert second[-2].tool_calls[0]["id"] == second[-1].tool_call_id
    assert response["context"] == {
        "history_turns_received": 20,
        "history_turns_used": 18,
        "history_turns_trimmed": 2,
    }
    assert model.invocation_options == [{"max_tokens": 2048}] * 2
    assert any(t["event"] == "context_trim" for t in response["trace"])
    assert len(history) == 20


def test_provider_overflow_trims_oldest_until_accepted(corpus):
    model = ScriptedModel(
        ProviderError("sensitive context details", code="context_length_exceeded"),
        ProviderError("maximum context length exceeded"),
        greeting(),
    )
    fresh = ScriptedModel(greeting())
    models = iter([model, fresh])
    service = ChatService(Settings(data_dir=corpus[1].parent), lambda _: next(models))
    history = [HistoryTurn(question=q, answer="A") for q in ["Old", "New"]]
    result = service.chat("Now", history, include_trace=True)
    assert [
        [m.content for m in batch if isinstance(m, HumanMessage)] for batch in model.inputs
    ] == [["Old", "New", "Now"], ["New", "Now"], ["Now"]]
    assert result["context"]["history_turns_trimmed"] == 2
    assert "sensitive" not in str(result)
    # The next request starts with its supplied pairs, not the prior trimmed state.
    assert service.chat("Next", history)["context"]["history_turns_used"] == 2
    assert [m.content for m in fresh.inputs[0] if isinstance(m, HumanMessage)] == [
        "Old",
        "New",
        "Next",
    ]


def test_overflow_retries_stop_when_all_historical_pairs_are_removed(corpus):
    error = ProviderError("prompt is too long")
    model = ScriptedModel(error, error, error, greeting())
    service = ChatService(Settings(data_dir=corpus[1].parent), lambda _: model)
    with pytest.raises(ContextWindowError):
        service.chat("Now", [HistoryTurn(question="Q", answer="A")] * 2)
    assert len(model.inputs) == 3
    assert [m.content for m in model.inputs[-1] if isinstance(m, HumanMessage)] == ["Now"]


@pytest.mark.parametrize(
    "error",
    [
        ProviderError("context length exceeded", status=401),
        ProviderError("context length exceeded", status=429),
        ProviderError("invalid tool schema", status=400),
        RuntimeError("network timeout"),
    ],
)
def test_unrelated_errors_are_not_retried_or_trimmed(corpus, error):
    model = ScriptedModel(error, greeting())
    service = ChatService(Settings(data_dir=corpus[1].parent), lambda _: model)
    with pytest.raises(type(error)):
        service.chat("Now", [HistoryTurn(question="Old", answer="A")])
    assert len(model.inputs) == 1


@pytest.mark.parametrize("provider_rejects", [False, True])
def test_no_history_left_returns_clear_422_without_leaking_provider_details(
    corpus, provider_rejects
):
    settings = Settings(data_dir=corpus[1].parent)
    model = ScriptedModel(ProviderError("secret debug text", code="context_length_exceeded"))
    if not provider_rejects:
        settings.chat_context_window_tokens = 2600  # Only 40 input tokens after reserve.
    service = ChatService(settings, lambda _: model)
    with TestClient(create_app(settings, service)) as client:
        response = client.post("/api/chat", json={"content": "Now"})
    assert response.status_code == 422
    assert "even without conversation history" in response.json()["detail"]
    assert "secret" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert len(model.inputs) == int(provider_rejects)


@pytest.mark.parametrize("message", ["prompt is too long", "input tokens exceed maximum limit"])
def test_provider_message_variants(message):
    assert is_context_overflow(ProviderError(message))
