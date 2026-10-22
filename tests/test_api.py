import pytest
from fastapi.testclient import TestClient
from policy_agent.api import create_app
from policy_agent.config import Settings
from policy_agent.retrieval import search


def test_api_evidence_and_metadata(corpus):
    _, db, _ = corpus
    with TestClient(create_app(Settings(data_dir=db.parent))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/knowledge").json()["documents"] == 1
        response = client.post("/api/knowledge/search", json={"query": "appeal suspension"})
        assert response.status_code == 200
        result = response.json()
        assert result["retrieval_mode"] == "keyword"
        assert "reinstatement form" in result["results"][0]["content"]
        assert result["results"][0]["source_url"].startswith("https://github.com/")


def test_unindexed_returns_actionable_error(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        response = client.post("/api/knowledge/search", json={"query": "appeal"})
        assert response.status_code == 503
        assert "index" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload", [{"query": ""}, {"query": "  "}, {"query": "appeal", "limit": 100}, {}]
)
def test_invalid_search_request_rejected(tmp_path, payload):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.post("/api/knowledge/search", json=payload).status_code == 422


@pytest.mark.parametrize(
    "query", ['" OR * NOT (', "你好", "the and or", "' ; DROP TABLE chunks;--"]
)
def test_query_syntax_cannot_break_index(corpus, query):
    _, db, _ = corpus
    search(db, query)
    assert search(db, "appeals")
