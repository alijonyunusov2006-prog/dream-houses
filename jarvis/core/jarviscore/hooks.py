"""Хуки Claude Code (PreToolUse / PostToolUse), опирающиеся на политику доступа.

Запуск из ``.claude/settings.json``::

    python core/jarviscore/hooks.py pre    # PreToolUse  → allow / ask / deny
    python core/jarviscore/hooks.py post   # PostToolUse → строка в журнал

Протокол хуков: JSON события на stdin. Для PreToolUse ответ в stdout вида
``{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", ...}}``.
Пустой stdout и код 0 — «решение не меняю». Любая ошибка внутри хука не должна
блокировать работу: пишем в stderr и выходим с 0.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # .../jarvis
ALLOWLIST = ROOT / "config" / "allowlist.toml"
LOG_DIR = ROOT / "data" / "logs"
ACTIONS_LOG = LOG_DIR / "actions.jsonl"

sys.path.insert(0, str(ROOT / "core"))
from jarviscore.policy import Decision, Policy  # noqa: E402


def _read_event() -> dict:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def _append_log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ACTIONS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def pre_tool_use(event: dict) -> dict | None:
    policy = Policy.load(ALLOWLIST)
    tool = event.get("tool_name", "")
    verdict = policy.check_tool_call(tool, event.get("tool_input") or {})
    _append_log({"hook": "pre", "tool": tool, "decision": verdict.decision.value, "reason": verdict.reason,
                 "session": event.get("session_id")})
    if verdict.decision is Decision.ALLOW:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": verdict.decision.value,
            "permissionDecisionReason": f"JARVIS policy: {verdict.reason}",
        }
    }


def post_tool_use(event: dict) -> None:
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    summary = tool_input.get("command") or tool_input.get("file_path") or tool_input.get("path") or ""
    _append_log({"hook": "post", "tool": tool, "input": str(summary)[:500], "session": event.get("session_id")})


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "pre"
    try:
        event = _read_event()
        if mode == "pre":
            out = pre_tool_use(event)
            if out is not None:
                print(json.dumps(out, ensure_ascii=False))
        else:
            post_tool_use(event)
    except Exception as exc:  # хук не должен ломать сессию
        print(f"jarvis hook error: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
