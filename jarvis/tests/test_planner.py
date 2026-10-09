from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from jarviscore.planner import Scheduler, State, Task


def now() -> datetime:
    return datetime.now(timezone.utc)


def make() -> Scheduler:
    s = Scheduler()
    s.add(Task("print-1", "Заказ на 3D-печать", priority=1, deadline=now() + timedelta(hours=6),
               estimate_min=120, resources=["printer:bambu-1"]))
    s.add(Task("model-1", "Модель комбайна", priority=1, estimate_min=180, resources=["gpu"]))
    s.add(Task("slice-1", "Нарезка в Bambu Studio", priority=1, depends_on=["model-1"], estimate_min=20))
    s.add(Task("crm-1", "CRM: этап авторизации", priority=2, estimate_min=240, resources=["claude"]))
    s.add(Task("insta-1", "Посты для Instagram", priority=3, estimate_min=60, resources=["claude"]))
    s.add(Task("render-1", "Рендер интерьера", priority=4, estimate_min=300, resources=["gpu"]))
    return s


def test_runnable_respects_dependencies_and_resources():
    s = make()
    ids = [t.id for t in s.runnable()]
    assert "slice-1" not in ids            # ждёт model-1
    assert ids[0] == "print-1"             # единственная с дедлайном идёт первой
    s.start("model-1")
    ids = [t.id for t in s.runnable()]
    assert "render-1" not in ids           # gpu занят моделью
    assert "crm-1" in ids and "insta-1" in ids


def test_start_blocks_resource_clash():
    s = make()
    s.start("crm-1")
    with pytest.raises(ValueError, match="ресурсы заняты"):
        s.start("insta-1")                 # оба хотят claude


def test_dependency_unlocks_after_completion():
    s = make()
    s.start("model-1")
    assert "slice-1" not in [t.id for t in s.runnable()]
    s.complete("model-1", progress="STL готов")
    assert "slice-1" in [t.id for t in s.runnable()]


def test_pause_resume_keeps_checkpoint():
    s = make()
    s.start("crm-1")
    s.pause("crm-1", checkpoint={"claude_session": "abc123"}, progress="сделана БД, идёт авторизация")
    t = s.tasks["crm-1"]
    assert t.state is State.PAUSED
    assert t.checkpoint["claude_session"] == "abc123"
    s.start("crm-1")
    assert t.state is State.RUNNING and t.attempts == 2


def test_preempt_pauses_lower_priority_on_shared_resource():
    s = make()
    s.start("render-1")                                     # p4 на gpu
    urgent = s.add(Task("model-2", "Срочная модель", priority=1, resources=["gpu"]))
    paused = s.preempt_for(urgent)
    assert [t.id for t in paused] == ["render-1"]
    assert s.tasks["render-1"].state is State.PAUSED
    s.start("model-2")


def test_fail_retries_then_asks_human():
    s = make()
    for _ in range(Scheduler.MAX_ATTEMPTS):
        s.start("insta-1")
        s.fail("insta-1", "нет ответа от Metricool")
    assert s.tasks["insta-1"].state is State.WAITING_HUMAN
    assert s.tasks["insta-1"].attempts == Scheduler.MAX_ATTEMPTS


def test_at_risk_detects_tight_deadline():
    s = Scheduler()
    s.add(Task("late", "Успеть", deadline=now() + timedelta(minutes=30), estimate_min=120))
    s.add(Task("ok", "Спокойно", deadline=now() + timedelta(days=2), estimate_min=60))
    s.add(Task("over", "Просрочено", deadline=now() - timedelta(minutes=5), estimate_min=10))
    risky = {t.id: why for t, why in s.at_risk()}
    assert "late" in risky and "over" in risky and "ok" not in risky
    assert "просрочена" in risky["over"]


def test_save_load_recover(tmp_path: Path):
    s = make()
    s.start("crm-1")
    p = tmp_path / "tasks.json"
    s.save(p)
    s2 = Scheduler.load(p)
    assert set(s2.tasks) == set(s.tasks)
    assert s2.tasks["crm-1"].state is State.RUNNING
    recovered = s2.recover()                                # «перезагрузка ПК»
    assert [t.id for t in recovered] == ["crm-1"]
    assert s2.tasks["crm-1"].state is State.PAUSED
    assert s2.tasks["print-1"].deadline is not None
