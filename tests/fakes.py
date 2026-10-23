"""Scripted test doubles. These never represent live-model quality."""

import json

from langchain_core.messages import AIMessage, ToolMessage


def call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "test-call"}])


def cited_answer(messages):
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            rows = json.loads(message.content).get("evidence", [])
            if rows:
                return call(
                    "submit_answer",
                    kind="answered",
                    answer=f"You can appeal using the form. [[{rows[0]['chunk_id']}]]",
                )
    raise AssertionError("Script expected retrieved evidence")


class ScriptedModel:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.inputs = []
        self.invocation_options = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages, **kwargs):
        self.inputs.append(list(messages))
        self.invocation_options.append(kwargs)
        if not self.responses:
            raise AssertionError("Scripted model exhausted")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response(messages) if callable(response) else response


class FakeEmbeddings:
    def __init__(self):
        self.document_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(texts)
        return [[0.1, 1.0] if "six months" in text else [1.0, 0.1] for text in texts]

    def embed_query(self, text):
        return [0.1, 1.0] if "期限" in text or "deadline" in text else [1.0, 0.1]
