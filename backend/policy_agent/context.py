"""Request-local context budgeting; discard oldest completed turns, never tool pairs."""

import math
import re
from dataclasses import dataclass

from langchain_core.messages import AnyMessage
from langchain_core.messages.utils import count_tokens_approximately

from policy_agent.config import Settings
from policy_agent.providers import ConfigurationError


class ContextWindowError(ValueError):
    """The current question and agent material cannot fit, even without history."""


CONTEXT_ERROR = (
    "The current question and tool context exceed the model context window, even without "
    "conversation history. Shorten the question or check the configured model context window."
)


def is_context_overflow(exc: Exception) -> bool:
    """Recognize provider context errors without retrying unrelated API failures."""
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    code = code or getattr(exc, "code", None)
    status = getattr(exc, "status_code", None)
    if status is not None and status not in (400, 413, 422):
        return False
    if code in {"context_length_exceeded", "context_window_exceeded", "prompt_too_long"}:
        return True
    if status not in (400, 413, 422):
        return False
    # Text is inspected only in memory, never added to responses or traces.
    return bool(
        re.search(
            r"maximum context length|context (?:window|length).*(?:exceed|too (?:long|large))"
            r"|(?:exceed|too (?:long|large)).*context (?:window|length)|prompt is too long"
            r"|input (?:is )?too long|input tokens?.*(?:exceed|maximum|limit)",
            str(exc),
            re.IGNORECASE,
        )
    )


@dataclass(frozen=True)
class ContextBudget:
    window: int
    output: int
    margin: int

    @classmethod
    def for_model(cls, settings: Settings, model):
        profile = getattr(model, "profile", None)
        profile_window = profile.get("max_input_tokens") if isinstance(profile, dict) else None
        window = settings.chat_context_window_tokens
        if not window:
            window = (
                profile_window if isinstance(profile_window, int) and profile_window > 0 else 32768
            )
        budget = cls(window, settings.chat_max_output_tokens, settings.chat_context_margin_tokens)
        if budget.output + budget.margin >= window:
            raise ConfigurationError(
                "POLICY_CHAT_CONTEXT_WINDOW_TOKENS must exceed the output token limit "
                "plus POLICY_CHAT_CONTEXT_MARGIN_TOKENS."
            )
        return budget

    @property
    def input_limit(self):
        return self.window - self.output - self.margin

    def estimate(self, messages: list[AnyMessage], tools: list) -> int:
        # Local, provider-independent approximation: conservative for English, with
        # an additional UTF-8 allowance for Chinese and other non-ASCII text.
        # Actual provider rejection remains the backstop; no tokenizer downloads.
        tokens = count_tokens_approximately(messages, tools=tools, chars_per_token=2)
        non_ascii_bytes = sum(
            len(str(m.content).encode("utf-8")) - len(str(m.content)) for m in messages
        )
        return tokens + math.ceil(non_ascii_bytes / 2)

    def fit(self, system: AnyMessage, messages: list[AnyMessage], turns: int, tools: list):
        messages = list(messages)
        while True:
            estimate = self.estimate([system, *messages], tools)
            if estimate <= self.input_limit:
                return messages, turns, estimate
            if not turns:
                raise ContextWindowError(CONTEXT_ERROR)
            # Only the prefix is caller-owned history: one human + one AI per turn.
            del messages[:2]
            turns -= 1
