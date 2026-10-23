import pytest
from policy_agent.setup import main


def test_initialization_script_has_no_chat_or_resume_entry(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["setup", "chat"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    monkeypatch.setattr("sys.argv", ["setup", "--help"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "{sync,index,embed,status}" in help_text
    assert "--conversation" not in help_text
