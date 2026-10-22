from fastapi.testclient import TestClient
from policy_agent.api import create_app
from policy_agent.config import Settings
from policy_agent.conversations import ConversationService

from tests.fakes import ScriptedModel, call, cited_answer


def test_conversation_endpoints(corpus):
    settings = Settings(data_dir=corpus[1].parent)
    model = ScriptedModel(call("search_policies", query="appeals"), cited_answer)
    service = ConversationService(settings, lambda _: model)
    with TestClient(create_app(settings, service)) as client:
        created = client.post("/api/conversations")
        assert created.status_code == 201
        key = created.json()["id"]
        assert client.get("/api/conversations").json()["conversations"][0]["id"] == key
        response = client.post(
            f"/api/conversations/{key}/messages", json={"content": "Can I appeal?"}
        )
        assert response.status_code == 200
        assert response.json()["citations"]
        listed = client.get("/api/conversations").json()["conversations"][0]
        assert listed["title"] == "Can I appeal?"
        assert listed["turn_count"] == 1
        assert len(client.get(f"/api/conversations/{key}").json()["turns"]) == 1
        assert client.delete(f"/api/conversations/{key}").status_code == 204
        assert client.get(f"/api/conversations/{key}").status_code == 404
        assert (
            client.post(f"/api/conversations/{key}/messages", json={"content": "Hi"}).status_code
            == 404
        )


def test_provider_error_is_sanitized_and_retryable(corpus):
    settings = Settings(data_dir=corpus[1].parent)
    model = ScriptedModel(RuntimeError("sensitive-provider-debug-detail"))
    service = ConversationService(settings, lambda _: model)
    with TestClient(create_app(settings, service)) as client:
        key = client.post("/api/conversations").json()["id"]
        response = client.post(f"/api/conversations/{key}/messages", json={"content": "Question"})
        assert response.status_code == 502
        assert "sensitive-provider" not in response.text
        assert client.get(f"/api/conversations/{key}").json()["turns"] == []


def test_missing_configuration_and_invalid_message(corpus):
    settings = Settings(data_dir=corpus[1].parent, chat_model="", chat_provider="")
    with TestClient(create_app(settings)) as client:
        key = client.post("/api/conversations").json()["id"]
        assert (
            client.post(f"/api/conversations/{key}/messages", json={"content": " "}).status_code
            == 422
        )
        response = client.post(f"/api/conversations/{key}/messages", json={"content": "Hi"})
        assert response.status_code == 503
        assert "CHAT_PROVIDER" in response.text
