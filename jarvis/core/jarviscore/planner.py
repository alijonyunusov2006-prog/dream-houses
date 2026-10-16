"""Планировщик задач: приоритеты, дедлайны, зависимости, ресурсы, пауза и восстановление.

Модель намеренно простая и без базы данных: список задач сериализуется в JSON
(``data/tasks.json``), в этапе 3 тот же формат уезжает в Supabase.

Ресурсы — строки (``"gpu"``, ``"printer:bambu-1"``, ``"claude"``). Задача запускается,
только если все её ресурсы свободны и все зависимости завершены. Порядок выбора:
1) просроченные и ближайшие дедлайны, 2) приоритет, 3) время создания.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable


class State(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"      # ждёт зависимость или ресурс
    DONE = "done"
    FAILED = "failed"
    WAITING_HUMAN = "waiting_human"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Task:
    id: str
    title: str
    priority: int = 3                      # 1 — срочно, 5 — когда-нибудь
    deadline: datetime | None = None
    estimate_min: int = 30
    depends_on: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    project: str = ""
    state: State = State.PENDING
    progress: str = ""                     # свободный текст «что сделано», для возобновления
    checkpoint: dict = field(default_factory=dict)  # состояние для паузы (session_id и т.п.)
    attempts: int = 0
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    # --- сериализация -------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        for k in ("deadline", "created_at", "updated_at"):
            d[k] = d[k].isoformat() if d[k] else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        d = dict(d)
        d["state"] = State(d.get("state", "pending"))
        for k in ("deadline", "created_at", "updated_at"):
            d[k] = datetime.fromisoformat(d[k]) if d.get(k) else None
        d["created_at"] = d["created_at"] or _now()
        d["updated_at"] = d["updated_at"] or _now()
        return cls(**d)

    def touch(self) -> None:
        self.updated_at = _now()


class Scheduler:
    MAX_ATTEMPTS = 3

    def __init__(self, tasks: Iterable[Task] = ()):
        self.tasks: dict[str, Task] = {t.id: t for t in tasks}

    # --- хранение -----------------------------------------------------------
    def save(self, path: Path | str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps([t.to_dict() for t in self.tasks.values()],
                                         ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "Scheduler":
        p = Path(path)
        if not p.exists():
            return cls()
        return cls(Task.from_dict(d) for d in json.loads(p.read_text(encoding="utf-8")))

    def recover(self) -> list[Task]:
        """После перезапуска: всё, что было RUNNING, становится PAUSED с сохранённым чекпоинтом."""
        recovered = []
        for t in self.tasks.values():
            if t.state is State.RUNNING:
                t.state = State.PAUSED
                t.touch()
                recovered.append(t)
        return recovered

    # --- операции -----------------------------------------------------------
    def add(self, task: Task) -> Task:
        self.tasks[task.id] = task
        return task

    def busy_resources(self) -> set[str]:
        return {r for t in self.tasks.values() if t.state is State.RUNNING for r in t.resources}

    def deps_done(self, task: Task) -> bool:
        return all(self.tasks.get(d) is not None and self.tasks[d].state is State.DONE for d in task.depends_on)

    def runnable(self) -> list[Task]:
        """Задачи, которые можно запустить прямо сейчас, в порядке выбора."""
        busy = self.busy_resources()
        out = []
        for t in self.tasks.values():
            if t.state not in (State.PENDING, State.PAUSED, State.BLOCKED):
                continue
            if not self.deps_done(t):
                continue
            if any(r in busy for r in t.resources):
                continue
            out.append(t)
        far = _now() + timedelta(days=3650)
        out.sort(key=lambda t: (t.deadline or far, t.priority, t.created_at))
        return out

    def start(self, task_id: str) -> Task:
        t = self.tasks[task_id]
        if t.state not in (State.PENDING, State.PAUSED, State.BLOCKED):
            raise ValueError(f"{task_id}: нельзя запустить из состояния {t.state.value}")
        if not self.deps_done(t):
            raise ValueError(f"{task_id}: зависимости не завершены")
        clash = set(t.resources) & self.busy_resources()
        if clash:
            raise ValueError(f"{task_id}: ресурсы заняты: {sorted(clash)}")
        t.state = State.RUNNING
        t.attempts += 1
        t.touch()
        return t

    def pause(self, task_id: str, checkpoint: dict | None = None, progress: str = "") -> Task:
        t = self.tasks[task_id]
        if t.state is not State.RUNNING:
            raise ValueError(f"{task_id}: пауза возможна только из running")
        t.state = State.PAUSED
        if checkpoint:
            t.checkpoint.update(checkpoint)
        if progress:
            t.progress = progress
        t.touch()
        return t

    def complete(self, task_id: str, progress: str = "") -> Task:
        t = self.tasks[task_id]
        t.state = State.DONE
        if progress:
            t.progress = progress
        t.touch()
        return t

    def fail(self, task_id: str, reason: str) -> Task:
        """Ошибка → задача возвращается в очередь; после MAX_ATTEMPTS — вопрос человеку."""
        t = self.tasks[task_id]
        t.progress = f"ошибка: {reason}"
        t.state = State.WAITING_HUMAN if t.attempts >= self.MAX_ATTEMPTS else State.PENDING
        t.touch()
        return t

    def preempt_for(self, urgent: Task) -> list[Task]:
        """Срочная задача: приостановить работающие задачи, которые держат нужные ей ресурсы."""
        paused = []
        for t in self.tasks.values():
            if t.state is State.RUNNING and set(t.resources) & set(urgent.resources) and t.priority > urgent.priority:
                self.pause(t.id, progress=t.progress or "приостановлена ради срочной задачи")
                paused.append(t)
        return paused

    # --- сроки --------------------------------------------------------------
    def at_risk(self, now: datetime | None = None) -> list[tuple[Task, str]]:
        """Задачи, чей дедлайн под угрозой: оставшегося времени меньше оценки (с учётом очереди)."""
        now = now or _now()
        risks = []
        for t in self.tasks.values():
            if t.state in (State.DONE, State.FAILED) or not t.deadline:
                continue
            remaining = (t.deadline - now).total_seconds() / 60
            if remaining < 0:
                risks.append((t, f"просрочена на {int(-remaining)} мин"))
            elif remaining < t.estimate_min:
                risks.append((t, f"осталось {int(remaining)} мин, нужно ≈{t.estimate_min}"))
        return risks
