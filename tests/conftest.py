import json
import subprocess

import pytest
from policy_agent.config import Settings
from policy_agent.ingestion import index_source

POLICY = """---
title: Example appeals policy
---
## Appeals

Users can appeal an account suspension using the reinstatement form.

## Deadlines

Appeals may be submitted within six months following the decision.
"""


@pytest.fixture(autouse=True)
def isolate_local_configuration(monkeypatch):
    """Local .env credentials must never turn deterministic tests into paid calls."""
    for name, field in Settings.model_fields.items():
        value = field.get_default(call_default_factory=True)
        encoded = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        monkeypatch.setenv(f"POLICY_{name.upper()}", encoded)


@pytest.fixture
def corpus(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    policy = repo / "Policies" / "appeals.md"
    policy.parent.mkdir()
    policy.write_text(POLICY, encoding="utf-8")

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

    git("init", "--quiet")
    git("add", ".")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "test fixture",
    )
    commit = git("rev-parse", "HEAD")
    lock = tmp_path / "corpus.lock.json"
    lock.write_text(
        json.dumps({"commit": commit, "include": "Policies/**/*.md", "parser_version": 1}),
        encoding="utf-8",
    )
    db = tmp_path / "policies.sqlite3"
    index_source(repo, db, lock)
    return repo, db, lock
