import pytest
from policy_agent.config import Settings
from policy_agent.ingestion import index_source
from policy_agent.providers import ConfigurationError
from policy_agent.semantic import Retriever, build_embeddings, normalize

from tests.fakes import FakeEmbeddings


def configured(corpus):
    return Settings(
        data_dir=corpus[1].parent,
        retrieval_mode="hybrid",
        embedding_provider="scripted",
        embedding_model="test-v1",
    )


def test_semantic_retrieval_and_cache_reuse(corpus):
    settings = configured(corpus)
    embedder = FakeEmbeddings()
    manifest = build_embeddings(settings, embedder, batch_size=1)
    assert manifest["embedded_now"] == 2
    assert len(embedder.document_calls) == 2
    assert build_embeddings(settings, embedder)["embedded_now"] == 0
    assert len(embedder.document_calls) == 2
    rows = Retriever(settings, lambda _: embedder).search("申诉期限", limit=1)
    assert "six months" in rows[0]["content"]
    assert "vector" not in rows[0]


def test_hybrid_rejects_missing_index_and_changed_model(corpus):
    settings = configured(corpus)
    retriever = Retriever(settings, lambda _: FakeEmbeddings())
    with pytest.raises(ConfigurationError, match="embedding index"):
        retriever.search("appeals")
    build_embeddings(settings, FakeEmbeddings())
    changed = settings.model_copy(update={"embedding_model": "different"})
    with pytest.raises(ConfigurationError, match="configuration changed"):
        Retriever(changed).search("appeals")


def test_dimension_mismatch_is_actionable(corpus):
    settings = configured(corpus)
    build_embeddings(settings, FakeEmbeddings())
    embedder = FakeEmbeddings()
    embedder.embed_query = lambda text: [1, 0, 0]
    with pytest.raises(ConfigurationError, match="dimensions changed"):
        Retriever(settings, lambda _: embedder).search("appeals")


def test_failed_build_preserves_previous_index(corpus):
    settings = configured(corpus)
    build_embeddings(settings, FakeEmbeddings())
    broken = FakeEmbeddings()
    broken.embed_documents = lambda texts: [[0, 0] for _ in texts]
    changed = settings.model_copy(update={"embedding_model": "broken"})
    with pytest.raises(ConfigurationError, match="nonzero"):
        build_embeddings(changed, broken)
    assert Retriever(settings, lambda _: FakeEmbeddings()).search("appeals")


def test_reindex_invalidates_embeddings(corpus):
    settings = configured(corpus)
    build_embeddings(settings, FakeEmbeddings())
    index_source(*corpus)
    with pytest.raises(ConfigurationError, match="embedding index"):
        Retriever(settings).search("appeals")


def test_neighboring_section_restores_missing_qualifying_clause(corpus):
    retriever = Retriever(Settings(data_dir=corpus[1].parent))
    seeds = retriever.search("suspension")
    assert not any("six months" in row["content"] for row in seeds)
    expanded = retriever.search_with_context("suspension")
    assert any("six months" in row["content"] for row in expanded)
    assert all("source_url" in row for row in expanded)


@pytest.mark.parametrize(
    "values", [[[0, 0]], [[float("nan"), 1]], [[]], [[1, 2], [1]], [["text", 1]]]
)
def test_invalid_embeddings_rejected(values):
    with pytest.raises(ConfigurationError):
        normalize(values)
