import json
import os
import stat
import sys
from pathlib import Path

import pytest

from jarviscore import claude_runner as cr


def test_build_command_full():
    cmd = cr.build_command(
        "сделай список дел", model="sonnet", resume="sess-1", allowed_tools=["Read", "Edit", "Bash(npm test)"],
        max_turns=12, permission_mode="acceptEdits", add_dirs=["C:/Projects/todo"], append_system_prompt="Отвечай по-русски",
    )
    assert cmd[:5] == ["claude", "-p", "сделай список дел", "--output-format", "json"]
    assert "--model" in cmd and cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--resume") + 1] == "sess-1"
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Edit,Bash(npm test)"
    assert cmd[cmd.index("--max-turns") + 1] == "12"
    assert cmd[cmd.index("--add-dir") + 1] == "C:/Projects/todo"
    assert cmd[-1] == "Отвечай по-русски"


def test_parse_output_tolerates_prefix_noise():
    payload = {"type": "result", "result": "ok", "session_id": "s"}
    assert cr.parse_output("warming up...\n" + json.dumps(payload)) == payload
    assert cr.parse_output(json.dumps(payload)) == payload


@pytest.fixture
def fake_claude(tmp_path: Path) -> Path:
    """Поддельный `claude`: печатает JSON как настоящий `claude -p --output-format json`."""
    script = tmp_path / "claude"
    body = (
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "args = sys.argv[1:]\n"
        "prompt = args[args.index('-p') + 1]\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,"
        " 'duration_ms': 1234, 'num_turns': 3, 'result': 'done: ' + prompt,"
        " 'session_id': 'sess-42', 'total_cost_usd': 0.25}))\n"
    )
    script.write_text(body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.mark.skipif(sys.platform == "win32", reason="shebang-скрипт; на Windows раннер проверяется с настоящим claude")
def test_run_parses_result_and_logs_cost(fake_claude: Path, tmp_path: Path):
    log = tmp_path / "costs.jsonl"
    res = cr.run("построй план", tmp_path, claude_bin=str(fake_claude), cost_log=log, task_id="t1", model="sonnet")
    assert res.ok and res.session_id == "sess-42" and res.cost_usd == 0.25 and res.num_turns == 3
    assert res.result == "done: построй план"
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["task"] == "t1" and rec["cost_usd"] == 0.25 and rec["model"] == "sonnet"
    assert cr.spent_today(log) == pytest.approx(0.25)


@pytest.mark.skipif(sys.platform == "win32", reason="shebang-скрипт")
def test_budget_stop(fake_claude: Path, tmp_path: Path):
    log = tmp_path / "costs.jsonl"
    cr.run("раз", tmp_path, claude_bin=str(fake_claude), cost_log=log)
    with pytest.raises(cr.BudgetExceeded):
        cr.run("два", tmp_path, claude_bin=str(fake_claude), cost_log=log, daily_budget_usd=0.20)


def test_missing_binary_is_clear_error(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="claude login"):
        cr.run("x", tmp_path, claude_bin="claude-definitely-missing", cost_log=tmp_path / "c.jsonl")
