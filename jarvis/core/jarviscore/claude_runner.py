"""Раннер Claude Code в headless-режиме (``claude -p``), работает по подписке.

Собирает команду, запускает её в папке проекта, разбирает JSON-ответ и пишет
стоимость в ``data/logs/costs.jsonl``. Никакой имитации нажатий: только штатный
интерфейс CLI. Требует установленный Claude Code (``claude`` в PATH) и выполненный
``claude login`` на ПК.

Формат ответа ``--output-format json`` (ключевые поля): ``result``, ``session_id``,
``total_cost_usd``, ``duration_ms``, ``num_turns``, ``is_error``, ``usage``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class RunResult:
    ok: bool
    result: str
    session_id: str | None
    cost_usd: float
    duration_ms: int
    num_turns: int
    raw: dict = field(default_factory=dict)
    stderr: str = ""


def build_command(
    prompt: str,
    *,
    model: str | None = None,
    resume: str | None = None,
    allowed_tools: Sequence[str] | None = None,
    disallowed_tools: Sequence[str] | None = None,
    max_turns: int | None = None,
    permission_mode: str | None = "acceptEdits",
    add_dirs: Sequence[str | Path] = (),
    append_system_prompt: str | None = None,
    claude_bin: str = "claude",
) -> list[str]:
    cmd = [claude_bin, "-p", prompt, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    if resume:
        cmd += ["--resume", resume]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if disallowed_tools:
        cmd += ["--disallowedTools", ",".join(disallowed_tools)]
    if max_turns:
        cmd += ["--max-turns", str(max_turns)]
    if permission_mode:
        cmd += ["--permission-mode", permission_mode]
    for d in add_dirs:
        cmd += ["--add-dir", str(d)]
    if append_system_prompt:
        cmd += ["--append-system-prompt", append_system_prompt]
    return cmd


def parse_output(stdout: str) -> dict:
    """JSON может быть окружён служебным текстом — берём последний JSON-объект."""
    stdout = stdout.strip()
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        start = stdout.rfind("\n{")
        if start == -1:
            raise
        return json.loads(stdout[start + 1:])


def _log_cost(log_path: Path, record: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def spent_today(log_path: Path) -> float:
    if not log_path.exists():
        return 0.0
    today = datetime.now(timezone.utc).date().isoformat()
    total = 0.0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("ts", "").startswith(today):
            total += float(rec.get("cost_usd") or 0.0)
    return total


def run(
    prompt: str,
    cwd: Path | str,
    *,
    timeout_sec: int = 3600,
    daily_budget_usd: float | None = None,
    cost_log: Path | str = "data/logs/costs.jsonl",
    task_id: str = "",
    **kwargs,
) -> RunResult:
    """Запустить Claude Code в папке ``cwd``.

    ``daily_budget_usd`` — стоп-кран: если сегодняшний эквивалент расходов уже выше
    порога, запуск не начинается (подписка не тратит деньги, но лимиты окон — тратит).
    """
    cost_log = Path(cost_log)
    if daily_budget_usd is not None and spent_today(cost_log) >= daily_budget_usd:
        raise BudgetExceeded(f"дневной порог {daily_budget_usd} $ уже израсходован")

    claude_bin = kwargs.pop("claude_bin", "claude")
    if shutil.which(claude_bin) is None and not Path(claude_bin).exists():
        raise FileNotFoundError("claude не найден в PATH — установите Claude Code и выполните `claude login`")

    cmd = build_command(prompt, claude_bin=claude_bin, **kwargs)
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout_sec)
    try:
        data = parse_output(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        data = {"is_error": True, "result": proc.stdout[-2000:]}

    res = RunResult(
        ok=(proc.returncode == 0 and not data.get("is_error", False)),
        result=str(data.get("result", "")),
        session_id=data.get("session_id"),
        cost_usd=float(data.get("total_cost_usd") or 0.0),
        duration_ms=int(data.get("duration_ms") or 0),
        num_turns=int(data.get("num_turns") or 0),
        raw=data,
        stderr=proc.stderr[-2000:],
    )
    _log_cost(cost_log, {"task": task_id, "cwd": str(cwd), "model": kwargs.get("model"),
                         "cost_usd": res.cost_usd, "turns": res.num_turns, "ms": res.duration_ms,
                         "ok": res.ok, "session": res.session_id})
    return res
