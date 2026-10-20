from datetime import datetime, timedelta, timezone

from jarviscore.controller import Controller
from jarviscore.planner import Scheduler, State

T0 = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)


def make(tmp_path, **kw):
    return Controller(Scheduler(), tmp_path / "tasks.json", **kw)


def test_new_task_gets_short_number_and_keeps_full_text(tmp_path):
    c = make(tmp_path)
    t1 = c.new_task("Сделай список дел с тегами и пришли скриншот", source="voice", now=T0)
    t2 = c.new_task("Второе", now=T0)
    assert (t1.id, t2.id) == ("1", "2")
    assert t1.checkpoint["text"].startswith("Сделай список дел")
    assert t1.checkpoint["source"] == "voice"
    assert t1.state is State.PENDING


def test_tasks_survive_restart_and_running_becomes_paused(tmp_path):
    c = make(tmp_path)
    t = c.new_task("Долгая задача", now=T0)
    c.sched.start(t.id)
    c.save()
    c2 = Controller.load(tmp_path / "tasks.json")
    assert c2.sched.tasks["1"].state is State.PAUSED
    assert c2.new_task("Ещё", now=T0).id == "2"


def test_question_waits_for_owner_and_answer_returns_task_to_queue(tmp_path):
    c = make(tmp_path)
    t = c.new_task("Сделай сайт", now=T0)
    c.ask(t.id, "Какие цвета?", ask_msg=555, now=T0)
    assert t.state is State.WAITING_HUMAN
    assert c.waiting_for_reply_to(555) is t
    c.answer(t.id, "Цвета Dream House", now=T0)
    assert t.state is State.PENDING
    assert t.checkpoint["answers"] == ["Цвета Dream House"]


def test_unanswered_question_escalates_after_ten_minutes_then_reminds_hourly(tmp_path):
    c = make(tmp_path, escalation_min=10, remind_every_min=60)
    t = c.new_task("Сделай сайт", now=T0)
    c.ask(t.id, "Какие цвета?", ask_msg=1, now=T0)
    assert c.check(T0 + timedelta(minutes=9)) == []
    alerts = c.check(T0 + timedelta(minutes=11))
    assert [a.kind for a in alerts] == ["escalate"]
    assert "Какие цвета?" in alerts[0].text
    assert c.check(T0 + timedelta(minutes=30)) == []          # не дёргать каждую минуту
    assert [a.kind for a in c.check(T0 + timedelta(minutes=72))] == ["escalate"]


def test_stalled_running_task_is_reported(tmp_path):
    c = make(tmp_path, stall_min=90)
    t = c.new_task("Рендер", now=T0)
    c.sched.start(t.id)
    t.updated_at = T0
    assert c.check(T0 + timedelta(minutes=60)) == []
    alerts = c.check(T0 + timedelta(minutes=95))
    assert [a.kind for a in alerts] == ["stalled"]


def test_overdue_deadline_is_reported_once_per_interval(tmp_path):
    c = make(tmp_path, remind_every_min=60)
    t = c.new_task("Отчёт клиенту", now=T0, deadline=T0 + timedelta(minutes=30))
    assert [a.kind for a in c.check(T0 + timedelta(minutes=40))] == ["deadline"]
    assert c.check(T0 + timedelta(minutes=50)) == []


def test_done_tasks_are_silent_and_not_in_open_list(tmp_path):
    c = make(tmp_path)
    t = c.new_task("Готовое", now=T0, deadline=T0)
    c.sched.complete(t.id, "сделано")
    assert c.check(T0 + timedelta(days=1)) == []
    assert c.open_tasks() == []


def test_several_tasks_can_run_at_once(tmp_path):
    c = make(tmp_path)
    a, b = c.new_task("Первая", now=T0), c.new_task("Вторая", now=T0)
    c.sched.start(a.id)
    assert [t.id for t in c.sched.runnable()] == [b.id]          # вторая не ждёт, пока первая закончит


def test_summary_lists_open_tasks_with_state_in_russian(tmp_path):
    c = make(tmp_path)
    c.new_task("Первая", now=T0)
    t = c.new_task("Вторая", now=T0)
    c.ask(t.id, "Вопрос?", ask_msg=2, now=T0)
    text = c.summary()
    assert "№1" in text and "в очереди" in text
    assert "№2" in text and "ждёт вашего ответа" in text


def test_reminders_stop_after_two(tmp_path):
    from datetime import timedelta
    from jarviscore.controller import Controller
    from jarviscore.planner import Scheduler
    ctl = Controller(Scheduler(), tmp_path / "t.json", escalation_min=0)
    ctl.remind_every_min = 0
    t = ctl.new_task("x")
    ctl.ask(t.id, "вопрос?")
    sent = [a for _ in range(5) for a in ctl.check()]
    assert len([a for a in sent if a.kind == "escalate"]) == 2
