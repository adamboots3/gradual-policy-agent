import pytest
from langchain import chat_models
from policy_agent.config import Settings
from policy_agent.providers import ConfigurationError, create_chat


def test_lazy_provider_settings_are_forwarded(monkeypatch):
    calls = []
    monkeypatch.setattr(chat_models, "init_chat_model", lambda *a, **kw: calls.append((a, kw)))
    create_chat(
        Settings(
            chat_provider="custom",
            chat_model="model-a",
            chat_api_key="test-secret",
            chat_base_url="https://example.invalid/v1",
        )
    )
    assert calls[0][1]["model_provider"] == "custom"
    assert calls[0][1]["api_key"] == "test-secret"


def test_missing_chat_config_is_explicit():
    with pytest.raises(ConfigurationError, match="CHAT_PROVIDER"):
        create_chat(Settings())


def test_provider_specific_body_is_forwarded(monkeypatch):
    captured = {}
    monkeypatch.setattr(chat_models, "init_chat_model", lambda *a, **kw: captured.update(kw))
    create_chat(
        Settings(
            chat_provider="openai",
            chat_model="compatible-tool-model",
            chat_extra_body={"thinking": {"type": "disabled"}},
        )
    )
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
