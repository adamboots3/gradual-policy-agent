import pytest
from langchain import chat_models, embeddings
from policy_agent.config import Settings
from policy_agent.providers import ConfigurationError, create_chat, create_embeddings


def test_lazy_provider_settings_are_forwarded(monkeypatch):
    calls = []
    monkeypatch.setattr(chat_models, "init_chat_model", lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr(embeddings, "init_embeddings", lambda *a, **kw: calls.append((a, kw)))
    settings = Settings(
        chat_provider="custom",
        chat_model="model-a",
        chat_api_key="test-secret",
        chat_base_url="https://example.invalid/v1",
        embedding_provider="custom-emb",
        embedding_model="model-b",
        embedding_api_key="other-secret",
    )
    create_chat(settings)
    create_embeddings(settings)
    assert calls[0][1]["model_provider"] == "custom"
    assert calls[0][1]["api_key"] == "test-secret"
    assert calls[1][1]["provider"] == "custom-emb"
    assert calls[1][0] == ("model-b",)


def test_missing_embedding_config_is_explicit():
    with pytest.raises(ConfigurationError, match="EMBEDDING_PROVIDER"):
        create_embeddings(Settings(embedding_provider="", embedding_model=""))


def test_provider_specific_body_is_forwarded(monkeypatch):
    captured = {}

    def initialize(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(chat_models, "init_chat_model", initialize)
    create_chat(
        Settings(
            chat_provider="openai",
            chat_model="deepseek-flash",
            chat_extra_body={"thinking": {"type": "disabled"}},
        )
    )
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_compatible_embedding_adapter_uses_raw_strings_and_small_batches(monkeypatch):
    captured = {}

    def initialize(*args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(embeddings, "init_embeddings", initialize)
    create_embeddings(Settings(embedding_provider="openai", embedding_model="text-embedding-v4"))
    assert captured["check_embedding_ctx_length"] is False
    assert captured["chunk_size"] == 10
    assert captured["model_kwargs"]["encoding_format"] == "float"
