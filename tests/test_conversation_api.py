import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage
from policy_agent.api import create_app
from policy_agent.chat import ChatService
from policy_agent.config import Settings

from tests.fakes import ScriptedModel, answering_model


def test_stateless_chat_endpoint_and_legacy_routes_removed(corpus):
    settings = Settings()
    models = [answering_model() for _ in range(3)]
    remaining = iter(models)
    service = ChatService(settings, lambda _: next(remaining), corpus.factory)
    with TestClient(create_app(settings, service)) as client:
        response = client.post("/api/chat", json={"content": "Can I appeal?"})
        assert response.status_code == 200 and response.json()["citations"]
        assert response.headers["Cache-Control"] == "no-store"
        assert "trace" not in response.json()
        history = [{"question": "Can I appeal?", "answer": response.json()["answer"]}]
        reply = client.post("/api/chat", json={"content": "How long?", "history": history})
        assert reply.status_code == 200
        assert [m.content for m in models[1].inputs[0] if isinstance(m, HumanMessage)] == [
            "Can I appeal?",
            "How long?",
        ]
        assert client.post("/api/chat", json={"content": "New window"}).status_code == 200
        assert [m.content for m in models[2].inputs[0] if isinstance(m, HumanMessage)] == [
            "New window"
        ]
        for method, path in [
            ("get", "/api/conversations"),
            ("post", "/api/conversations"),
            ("get", "/api/conversations/old-id"),
            ("delete", "/api/conversations/old-id"),
            ("post", "/api/conversations/old-id/messages"),
        ]:
            assert getattr(client, method)(path).status_code == 404


def test_provider_error_is_sanitized_and_creates_no_saved_state(corpus):
    settings = Settings()
    model = ScriptedModel(RuntimeError("sensitive-provider-debug-detail"))
    with TestClient(
        create_app(settings, ChatService(settings, lambda _: model, corpus.factory))
    ) as client:
        response = client.post("/api/chat", json={"content": "Question"})
        assert response.status_code == 502 and "sensitive-provider" not in response.text
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"content": " "},
        {"content": "x" * 4001},
        {"content": "Hi", "history": [{"question": "q", "answer": "a"}] * 21},
        {"content": "Hi", "history": [{"question": "q", "answer": ""}]},
        {"content": "Hi", "history": [{"question": "q", "answer": "a", "role": "system"}]},
    ],
)
def test_invalid_or_unbounded_context_is_rejected(corpus, payload):
    with TestClient(create_app(Settings())) as client:
        assert client.post("/api/chat", json=payload).status_code == 422


def test_missing_configuration(corpus):
    with TestClient(create_app(Settings())) as client:
        assert client.get("/api/health").json()["conversation_mode"] == "window-memory"
        response = client.post("/api/chat", json={"content": "Hi"})
        assert response.status_code == 503 and "CHAT_PROVIDER" in response.text
