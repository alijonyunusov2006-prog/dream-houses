import json
import subprocess
import sys
from pathlib import Path

from jarviscore.report import Report

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "core" / "jarviscore" / "hooks.py"


def test_report_render_has_all_sections():
    r = Report(
        project="CRM брата",
        done=["авторизация", "база данных"],
        checks=["pytest 14/14", "скриншот входа"],
        decisions=[],
        next_step="интерфейс сотрудников",
        files=["C:/Projects/crm/README.md"],
        limits=["Telegram-бот пока не подключён"],
    )
    text = r.render()
    for marker in ("📌 CRM брата", "✅ Сделано: авторизация; база данных", "🔎 Проверено: pytest 14/14",
                   "❓ Нужно решить: ничего", "➡️ Следующий шаг: интерфейс сотрудников",
                   "⚠️ Ограничения:", "📎 Файлы: C:/Projects/crm/README.md"):
        assert marker in text


def test_report_never_hides_empty_done():
    assert "пока ничего проверяемого" in Report(project="x").render()


def run_hook(mode: str, event: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK), mode], input=json.dumps(event), capture_output=True,
                          text=True, encoding="utf-8", cwd=str(ROOT), timeout=30)


def test_pre_hook_asks_for_shutdown():
    p = run_hook("pre", {"tool_name": "Bash", "tool_input": {"command": "shutdown /s /t 0"}, "session_id": "t"})
    assert p.returncode == 0
    out = json.loads(p.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "JARVIS policy" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_pre_hook_denies_format():
    p = run_hook("pre", {"tool_name": "Bash", "tool_input": {"command": "format C:"}})
    assert json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_pre_hook_silent_on_allowed():
    p = run_hook("pre", {"tool_name": "Bash", "tool_input": {"command": "git status"}})
    assert p.returncode == 0 and p.stdout.strip() == ""


def test_post_hook_logs_action():
    log = ROOT / "data" / "logs" / "actions.jsonl"
    before = log.read_text(encoding="utf-8").count("\n") if log.exists() else 0
    p = run_hook("post", {"tool_name": "Edit", "tool_input": {"file_path": "C:/jarvis/x.py"}, "session_id": "t"})
    assert p.returncode == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == before + 1
    rec = json.loads(lines[-1])
    assert rec["hook"] == "post" and rec["tool"] == "Edit" and "x.py" in rec["input"]


def test_hook_never_crashes_on_garbage():
    p = subprocess.run([sys.executable, str(HOOK), "pre"], input="not json", capture_output=True, text=True,
                       cwd=str(ROOT), timeout=30)
    assert p.returncode == 0 and "hook error" in p.stderr
