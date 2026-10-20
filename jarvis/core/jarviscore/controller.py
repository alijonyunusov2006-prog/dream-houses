"""Контролёр заданий: ничего не теряется и не забывается.

Поверх планировщика (``planner.Scheduler``) ведёт задания владельца: короткие номера,
вопросы владельцу и ответы на них, и раз в минуту смотрит, что пошло не так:

- ``escalate`` — вопрос владельцу без ответа дольше ``escalation_min`` (правило: 10 минут → звонок;
  пока звонков нет — повторное сообщение «срочно»);
- ``stalled``  — задача в работе дольше ``stall_min`` без движения;
- ``deadline`` — срок под угрозой или просрочен.

Одна и та же тревога по задаче повторяется не чаще ``remind_every_min``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .planner import Scheduler, State, Task

STATE_RU = {
    State.PENDING: "в очереди",
    State.RUNNING: "в работе",
    State.PAUSED: "на паузе",
    State.BLOCKED: "ждёт другую задачу",
    State.WAITING_HUMAN: "ждёт вашего ответа",
    State.DONE: "сделано",
    State.FAILED: "не получилось",
}
OPEN = (State.PENDING, State.RUNNING, State.PAUSED, State.BLOCKED, State.WAITING_HUMAN)
MAX_REMINDERS = 2          # одно и то же напоминание — не больше двух раз (урок 2026-10-21: «Конец.» ждёт 130 мин)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Alert:
    kind: str          # escalate | stalled | deadline
    task_id: str
    text: str


class Controller:
    def __init__(self, sched: Scheduler, path: Path | str, *, escalation_min: int = 10,
                 stall_min: int = 90, remind_every_min: int = 60):
        self.sched, self.path = sched, Path(path)
        self.escalation_min, self.stall_min, self.remind_every_min = escalation_min, stall_min, remind_every_min

    @classmethod
    def load(cls, path: Path | str, **kw) -> "Controller":
        sched = Scheduler.load(path)
        sched.recover()
        return cls(sched, path, **kw)

    def save(self) -> None:
        self.sched.save(self.path)

    # --- задания -------------------------------------------------------------
    def _next_id(self) -> str:
        nums = [int(i) for i in self.sched.tasks if i.isdigit()]
        return str(max(nums, default=0) + 1)

    def new_task(self, text: str, *, source: str = "text", priority: int = 3,
                 deadline: datetime | None = None, now: datetime | None = None) -> Task:
        now = now or _now()
        title = " ".join(text.split())[:60]
        t = Task(id=self._next_id(), title=title, priority=priority, deadline=deadline,
                 resources=[], checkpoint={"text": text, "source": source, "answers": []},
                 created_at=now, updated_at=now)
        return self.sched.add(t)

    def ask(self, task_id: str, question: str, *, ask_msg: int | None = None, now: datetime | None = None) -> Task:
        t = self.sched.tasks[task_id]
        t.state = State.WAITING_HUMAN
        t.checkpoint.update(question=question, ask_msg=ask_msg, asked_at=(now or _now()).isoformat())
        t.checkpoint.pop("alerts", None)
        t.updated_at = now or _now()
        return t

    def answer(self, task_id: str, text: str, *, now: datetime | None = None) -> Task:
        t = self.sched.tasks[task_id]
        t.checkpoint.setdefault("answers", []).append(text)
        for k in ("question", "ask_msg", "asked_at", "alerts"):
            t.checkpoint.pop(k, None)
        t.state = State.PENDING
        t.updated_at = now or _now()
        return t

    def waiting_for_reply_to(self, message_id: int) -> Task | None:
        for t in self.sched.tasks.values():
            if t.state is State.WAITING_HUMAN and t.checkpoint.get("ask_msg") == message_id:
                return t
        return None

    def waiting(self) -> list[Task]:
        return [t for t in self.sched.tasks.values() if t.state is State.WAITING_HUMAN]

    def open_tasks(self) -> list[Task]:
        return [t for t in self.sched.tasks.values() if t.state in OPEN]

    # --- проверка ------------------------------------------------------------
    def _due(self, t: Task, kind: str, now: datetime) -> bool:
        if t.checkpoint.get("alerts_n", {}).get(kind, 0) >= MAX_REMINDERS:   # не надоедать: два раза и хватит
            return False
        last = t.checkpoint.get("alerts", {}).get(kind)
        return last is None or now - datetime.fromisoformat(last) >= timedelta(minutes=self.remind_every_min)

    def _mark(self, t: Task, kind: str, now: datetime) -> None:
        t.checkpoint.setdefault("alerts", {})[kind] = now.isoformat()
        n = t.checkpoint.setdefault("alerts_n", {})
        n[kind] = n.get(kind, 0) + 1

    def unmark(self, alert: Alert) -> None:
        """Тревога не дошла до владельца — снять отметку, чтобы следующая проверка повторила её."""
        t = self.sched.tasks.get(alert.task_id)
        if t:
            t.checkpoint.get("alerts", {}).pop(alert.kind, None)
            n = t.checkpoint.get("alerts_n", {})
            if n.get(alert.kind):
                n[alert.kind] -= 1                     # недошедшее напоминание не считается

    def check(self, now: datetime | None = None) -> list[Alert]:
        now = now or _now()
        alerts: list[Alert] = []
        for t in self.open_tasks():
            if t.state is State.WAITING_HUMAN and t.checkpoint.get("asked_at"):
                waited = now - datetime.fromisoformat(t.checkpoint["asked_at"])
                if waited >= timedelta(minutes=self.escalation_min) and self._due(t, "escalate", now):
                    alerts.append(Alert("escalate", t.id, f"Срочно, задача №{t.id} «{t.title}» ждёт вас "
                                                          f"{int(waited.total_seconds() // 60)} мин: {t.checkpoint.get('question', '')}"))
                    self._mark(t, "escalate", now)
            if t.state is State.RUNNING and now - t.updated_at >= timedelta(minutes=self.stall_min) \
                    and self._due(t, "stalled", now):
                alerts.append(Alert("stalled", t.id, f"Задача №{t.id} «{t.title}» в работе без движения "
                                                     f"{int((now - t.updated_at).total_seconds() // 60)} мин — проверяю."))
                self._mark(t, "stalled", now)
        for t, why in self.sched.at_risk(now):
            if t.state in OPEN and self._due(t, "deadline", now):
                alerts.append(Alert("deadline", t.id, f"Срок задачи №{t.id} «{t.title}»: {why}."))
                self._mark(t, "deadline", now)
        return alerts

    def summary(self) -> str:
        items = sorted(self.open_tasks(), key=lambda t: int(t.id) if t.id.isdigit() else 0)
        if not items:
            return "Открытых задач нет."
        return "\n".join(f"№{t.id} · {STATE_RU[t.state]} · {t.title}" for t in items)
