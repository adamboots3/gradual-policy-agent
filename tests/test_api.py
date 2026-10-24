from fastapi.testclient import TestClient
from policy_agent.api import create_app
from policy_agent.chat import ChatService
from policy_agent.config import Settings
from policy_agent.github_source import PolicySourceError

from tests.fakes import ScriptedModel, call


def test_health_and_source_configuration_need_no_github_or_model_calls(corpus):
    settings = Settings()
    service = ChatService(settings, lambda _: None, corpus.factory)
    with TestClient(create_app(settings, service)) as client:
        health = client.get("/api/health").json()
        assert health["source_mode"] == "github-online" and "stage" not in health
        assert client.get("/api/policies").json() == {
            "repository": "https://github.com/github/site-policy",
            "ref": "HEAD",
            "source_mode": "github-online",
        }
        assert client.get("/api/knowledge").status_code == 404
        assert client.post("/api/knowledge/search", json={"query": "appeal"}).status_code == 404
    assert corpus.calls == []


def test_online_source_failure_is_clear_and_no_store(corpus):
    def broken(_):
        raise PolicySourceError("Cannot read GitHub policies. Check network access and retry.")

    corpus.respond = broken
    settings = Settings()
    service = ChatService(
        settings, lambda _: ScriptedModel(call("list_policy_documents")), corpus.factory
    )
    with TestClient(create_app(settings, service)) as client:
        response = client.post("/api/chat", json={"content": "Can I appeal?"})
    assert response.status_code == 503 and "GitHub" in response.json()["detail"]
    assert response.headers["Cache-Control"] == "no-store"
