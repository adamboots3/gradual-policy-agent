"""Request-scoped chat: callers own temporary context; no dialogue is stored."""

import time
from collections.abc import Sequence
from typing import Annotated
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, StringConstraints

from policy_agent.agent import PROMPT_VERSION, build_agent
from policy_agent.config import Settings
from policy_agent.github_source import PolicyRepository
from policy_agent.providers import create_chat


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)]


class ChatService:
    def __init__(
        self, settings: Settings, model_factory=create_chat, repository_factory=PolicyRepository
    ):
        self.settings = settings
        self.model_factory = model_factory
        self.repository_factory = repository_factory

    def chat(
        self,
        question: str,
        history: Sequence[HistoryTurn] = (),
        *,
        include_trace: bool = False,
    ) -> dict:
        if not question.strip() or len(question) > 4000:
            raise ValueError("Question must contain 1–4000 characters.")
        if len(history) > 20:
            raise ValueError("At most 20 completed context turns are accepted.")
        messages = []
        for turn in history:
            turn = HistoryTurn.model_validate(turn)
            messages.extend([HumanMessage(content=turn.question), AIMessage(content=turn.answer)])
        messages.append(HumanMessage(content=question.strip()))
        started = time.perf_counter()
        # Every invocation starts fresh, without a checkpointer or shared dialogue state.
        with self.repository_factory(self.settings) as repository:
            graph = build_agent(self.model_factory(self.settings), repository, self.settings)
            state = graph.invoke(
                {
                    "messages": messages,
                    "history_turns": len(history),
                    "evidence": {},
                    "read_calls": 0,
                    "directory_calls": 0,
                    "model_calls": 0,
                    "result": {},
                    "trace": [],
                    "question": question.strip(),
                },
                {"recursion_limit": 70},
            )
            commit = repository.commit
        result = {
            **state["result"],
            "run_id": str(uuid4()),
            "source_commit": commit,
            "source_mode": "github-online",
            "directory_calls": state["directory_calls"],
            "prompt_version": PROMPT_VERSION,
            "model": self.settings.chat_model,
            "provider": self.settings.chat_provider,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "model_calls": state["model_calls"],
            "context": {
                "history_turns_received": len(history),
                "history_turns_used": state["history_turns"],
                "history_turns_trimmed": len(history) - state["history_turns"],
            },
        }
        if include_trace:
            # Explicit evaluation output only; ordinary chat never saves or returns traces.
            result["trace"] = state["trace"]
        return result
