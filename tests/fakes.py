"""Scripted test doubles. These never represent live-model quality."""

import base64
import hashlib
import json

import httpx
from langchain_core.messages import AIMessage, ToolMessage
from policy_agent.github_source import PolicyRepository


def call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "test-call"}])


def cited_answer(messages):
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            row = json.loads(message.content)
            if "source_id" in row:
                return call(
                    "submit_answer",
                    kind="answered",
                    answer="You can appeal using the form. [[1]]",
                    citations=[
                        {
                            "source_id": row["source_id"],
                            "start_line": row["start_line"],
                            "end_line": min(row["end_line"], row["start_line"] + 79),
                        }
                    ],
                )
    raise AssertionError("Script expected a current-turn document read")


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


POLICY = """# Example appeals policy

Users can appeal an account suspension using the reinstatement form.

## Deadlines

Appeals may be submitted within six months following the decision.
"""


class GitHubFixture:
    commit = "a" * 40
    tree = "b" * 40

    def __init__(self):
        self.files = {
            "Policies/appeals.md": POLICY,
            "Policies/privacy/privacy-policy.md": "# Privacy\n\nPrivacy policy text.\n",
        }
        self.calls = []

    @staticmethod
    def digest(raw):
        return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

    def respond(self, request):
        self.calls.append(request)
        path = request.url.path
        if "/commits/" in path:
            return httpx.Response(
                200, json={"sha": self.commit, "commit": {"tree": {"sha": self.tree}}}
            )
        if "/git/trees/" in path:
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {
                            "path": p,
                            "sha": self.digest(t.encode()),
                            "size": len(t.encode()),
                            "type": "blob",
                            "mode": "100644",
                        }
                        for p, t in self.files.items()
                    ],
                },
            )
        for text in self.files.values():
            raw = text.encode()
            if path.endswith("/git/blobs/" + self.digest(raw)):
                return httpx.Response(
                    200, json={"encoding": "base64", "content": base64.b64encode(raw).decode()}
                )
        return httpx.Response(404)

    def factory(self, settings):
        return PolicyRepository(settings, transport=httpx.MockTransport(self.respond))


def answering_model():
    return ScriptedModel(
        call("list_policy_documents"),
        call("read_policy_document", path="Policies/appeals.md"),
        cited_answer,
    )
