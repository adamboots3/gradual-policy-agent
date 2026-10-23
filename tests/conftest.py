import json

import pytest
from policy_agent.config import Settings

from tests.fakes import GitHubFixture


@pytest.fixture(autouse=True)
def isolate_local_configuration(monkeypatch):
    """Never allow local credentials to turn deterministic tests into paid calls."""
    for name, field in Settings.model_fields.items():
        value = field.get_default(call_default_factory=True)
        encoded = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        monkeypatch.setenv(f"POLICY_{name.upper()}", encoded)


@pytest.fixture
def corpus():
    return GitHubFixture()
