"""Lazy LangChain provider factories; no network activity at application startup."""

from policy_agent.config import Settings


class ConfigurationError(ValueError):
    pass


def create_chat(settings: Settings):
    from langchain.chat_models import init_chat_model

    if not settings.chat_provider or not settings.chat_model:
        raise ConfigurationError("Set POLICY_CHAT_PROVIDER and POLICY_CHAT_MODEL in .env first.")
    kwargs = {"timeout": 60, "max_retries": 1}
    if settings.chat_api_key:
        kwargs["api_key"] = settings.chat_api_key
    if settings.chat_base_url:
        kwargs["base_url"] = settings.chat_base_url
    if settings.chat_extra_body:
        kwargs["extra_body"] = settings.chat_extra_body
    try:
        return init_chat_model(settings.chat_model, model_provider=settings.chat_provider, **kwargs)
    except ImportError as exc:
        raise ConfigurationError(
            "Install the selected LangChain provider integration first."
        ) from exc
