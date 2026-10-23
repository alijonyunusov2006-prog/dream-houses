"""Политика доступа: разрешённые папки и программы, команды с подтверждением и запретом.

Источник правил — ``config/allowlist.toml`` (регулярные выражения и пути). Три исхода:

* ``ALLOW`` — обратимое действие внутри разрешённых границ, делать без вопросов;
* ``ASK``   — нужно подтверждение человека (кнопка в Telegram или ответ в чате);
* ``DENY``  — запрещено всегда, даже с подтверждением (форматирование диска и т.п.).

Проверка пути: любой путь вне ``[paths].allowed`` → ``DENY``. Проверка команды:
сначала ``deny``-шаблоны, затем ``ask``-шаблоны, иначе ``ALLOW``.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePath


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    reason: str = ""

    def __bool__(self) -> bool:  # allow → True, остальное → False
        return self.decision is Decision.ALLOW


def _expand(p: str) -> Path:
    """Раскрыть %VAR% и $VAR, ~ и привести к абсолютному пути."""
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()


@dataclass
class Policy:
    allowed_dirs: list[Path] = field(default_factory=list)
    allowed_programs: list[str] = field(default_factory=list)
    deny_patterns: list[re.Pattern[str]] = field(default_factory=list)
    ask_patterns: list[re.Pattern[str]] = field(default_factory=list)

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, allowlist_path: Path | str) -> "Policy":
        data = tomllib.loads(Path(allowlist_path).read_text(encoding="utf-8"))
        paths = data.get("paths", {}).get("allowed", [])
        programs = data.get("programs", {}).get("allowed", [])
        cmds = data.get("commands", {})
        return cls(
            allowed_dirs=[_expand(p) for p in paths],
            allowed_programs=[p.lower() for p in programs],
            deny_patterns=[re.compile(p) for p in cmds.get("deny", [])],
            ask_patterns=[re.compile(p) for p in cmds.get("ask", [])],
        )

    # ----------------------------------------------------------------- paths
    def check_path(self, path: Path | str) -> Verdict:
        target = _expand(str(path))
        for root in self.allowed_dirs:
            try:
                target.relative_to(root)
                return Verdict(Decision.ALLOW)
            except ValueError:
                continue
        return Verdict(Decision.DENY, f"путь вне разрешённых папок: {target}")

    # -------------------------------------------------------------- programs
    def check_program(self, exe: str) -> Verdict:
        # Пути могут приходить в Windows-виде даже на Linux (тесты, логи) — режем по обоим разделителям.
        name = re.split(r"[\\/]", exe.strip().strip('"'))[-1].lower()
        stem = PurePath(name).stem
        if name in self.allowed_programs or stem in self.allowed_programs:
            return Verdict(Decision.ALLOW)
        return Verdict(Decision.ASK, f"программа не в allow-list: {exe}")

    # -------------------------------------------------------------- commands
    def check_command(self, command: str) -> Verdict:
        for pat in self.deny_patterns:
            if pat.search(command):
                return Verdict(Decision.DENY, f"запрещённая команда ({pat.pattern})")
        for pat in self.ask_patterns:
            if pat.search(command):
                return Verdict(Decision.ASK, f"нужно подтверждение ({pat.pattern})")
        return Verdict(Decision.ALLOW)

    # ----------------------------------------------------------- tool calls
    def check_tool_call(self, tool_name: str, tool_input: dict) -> Verdict:
        """Единая точка для хуков Claude Code и локального агента."""
        if tool_name in {"Bash", "shell_exec"}:
            return self.check_command(str(tool_input.get("command", "")))
        if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit", "file_write", "apply_patch"}:
            p = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("notebook_path")
            if not p:
                return Verdict(Decision.ASK, "запись без пути")
            return self.check_path(p)
        return Verdict(Decision.ALLOW)
