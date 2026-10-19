from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from jarviscore.bot import ClaudeExecutor, JarvisBot, LimitReached
from jarviscore.controller import Controller
from jarviscore.planner import Scheduler, State

OWNER = 111


class FakeTG:
    def __init__(self, fail_on=None):
        self.sent = []
        self._mid = 1000
        self.fail_on = fail_on

    def send(self, chat_id, text, reply_to=None):
        if self.fail_on and self.fail_on in text:
            raise ConnectionError("Telegram недоступен")
        self._mid += 1
        self.sent.append((chat_id, text))
        return {"message_id": self._mid}

    def download(self, file_id, dest):
        dest.write_bytes(b"ogg")
        return dest


class FakeSTT:
    def transcribe(self, path):
        return "сделай список дел"


class FakeClaude:
    def __init__(self, questions=(), needs_owner=False, ok=True, risky_after_answers=False, on_execute=None):
        self.questions, self.needs_owner, self.ok = list(questions), needs_owner, ok
        self.risky_after_answers, self.on_execute = risky_after_answers, on_execute
        self.executed, self.understood = [], 0

    def understand(self, task):
        self.understood += 1
        answered = bool(task.checkpoint.get("answers"))
        risky = self.needs_owner or (self.risky_after_answers and answered)
        return {"understood": ["нужен список дел"], "questions": [] if answered else self.questions,
                "needs_owner": risky, "reason": "удаление" if risky else ""}

    def execute(self, task):
        self.executed.append(task.id)
        if self.on_execute:
            self.on_execute(task)
        return SimpleNamespace(ok=self.ok, result="✅ Сделано: список" if self.ok else "упал тест", session_id="s1")


def make(tmp_path, claude=None, owner=OWNER, tg=None):
    tg = tg or FakeTG()
    ctl = Controller(Scheduler(), tmp_path / "tasks.json")
    bot = JarvisBot(tg, ctl, claude or FakeClaude(), FakeSTT(), owner_chat=owner,
                    ideas_dir=tmp_path / "ideas", tmp_dir=tmp_path / "tmp")
    return bot, tg, ctl


def msg(text=None, chat=OWNER, **extra):
    m = {"message_id": 5, "chat": {"id": chat, "type": "private"}, "from": {"id": chat, "is_bot": False}}
    if text is not None:
        m["text"] = text
    m.update(extra)
    return {"update_id": 1, "message": m}


def reply(ctl, num, text):
    return msg(text, reply_to_message={"message_id": ctl.sched.tasks[num].checkpoint["ask_msg"]})


def texts(tg):
    return [t for _, t in tg.sent]


# --- приём -----------------------------------------------------------------------
def test_stranger_is_ignored(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("сделай что-нибудь", chat=999))
    assert tg.sent == [] and ctl.sched.tasks == {}


def test_without_owner_only_id_command_works(tmp_path):
    bot, tg, ctl = make(tmp_path, owner=None)
    bot.handle(msg("/id", chat=42))
    bot.handle(msg("сделай сайт", chat=42))
    assert len(tg.sent) == 1 and "42" in tg.sent[0][1]
    assert ctl.sched.tasks == {}


def test_text_creates_task_and_confirms_with_number(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Сделай список дел с тегами"))
    assert ctl.sched.tasks["1"].state is State.PENDING
    assert "№1" in tg.sent[-1][1]


def test_voice_is_transcribed_echoed_and_becomes_task(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg(voice={"file_id": "abc", "duration": 3}))
    assert any("сделай список дел" in t for t in texts(tg))
    assert ctl.sched.tasks["1"].checkpoint["source"] == "voice"


def test_idea_goes_to_brain_not_to_queue(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Идея: продавать макеты застройщикам"))
    files = list((tmp_path / "ideas").glob("*.md"))
    assert len(files) == 1 and "застройщикам" in files[0].read_text(encoding="utf-8")
    assert ctl.sched.tasks == {}


def test_tasks_command_lists_open_tasks(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Первая задача"))
    bot.handle(msg("/tasks"))
    assert "№1" in tg.sent[-1][1]


def test_greeting_gives_briefing_not_a_task(tmp_path):
    bot, tg, ctl = make(tmp_path, FakeClaude(questions=["Какие теги?"]))
    bot.handle(msg("Сделай список дел"))
    bot.work_once()                                              # №1 ждёт ответа
    ctl.new_task("Отчёт по Ашану")                               # №2 в очереди
    done = ctl.new_task("Старое"); ctl.sched.complete(done.id)   # №3 сделано
    n = len(ctl.sched.tasks)
    bot.handle(msg("я дома"))
    assert len(ctl.sched.tasks) == n                             # приветствие — не задача
    text = tg.sent[-1][1]
    assert "сэр" in text and "№1" in text and "ждут вашего решения" in text.lower()
    assert "1 в очереди" in text and "Сегодня сделано: 1" in text


@pytest.mark.parametrize("hour, word", [(3, "ночи"), (8, "утро"), (14, "день"), (20, "вечер"), (23, "ночи")])
def test_briefing_greets_by_time_of_day(tmp_path, hour, word):
    bot, tg, ctl = make(tmp_path)
    assert word in bot.briefing(datetime(2026, 10, 20, hour, 0, tzinfo=timezone.utc)).split("\n")[0]


def test_morning_report_once_a_day_after_report_hour(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.report_hour = 8
    assert not bot.maybe_morning(datetime(2026, 10, 20, 7, 59))
    assert bot.maybe_morning(datetime(2026, 10, 20, 8, 1))
    assert "Утренний доклад" in tg.sent[-1][1]
    assert not bot.maybe_morning(datetime(2026, 10, 20, 12, 0))          # второй раз в тот же день — нет
    assert bot.maybe_morning(datetime(2026, 10, 21, 9, 30))              # назавтра — снова


def test_recall_answers_from_notes_without_task(tmp_path):
    bot, tg, ctl = make(tmp_path)
    (tmp_path / "decided.md").write_text("| 2026-10-05 | Цены Qabat — на паузе |\n", encoding="utf-8")
    bot.memory_roots = [tmp_path]
    bot.handle(msg("Вспомни, что мы решили про цены Qabat"))
    assert "паузе" in tg.sent[-1][1] and ctl.sched.tasks == {}


def test_greeting_when_nothing_happened(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Привет"))
    assert "сэр" in tg.sent[-1][1] and ctl.sched.tasks == {}


# --- исполнение ------------------------------------------------------------------
def test_clear_task_is_understood_then_executed_and_reported(tmp_path):
    claude = FakeClaude()
    bot, tg, ctl = make(tmp_path, claude)
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    assert claude.executed == ["1"]
    assert ctl.sched.tasks["1"].state is State.DONE
    assert any("Вот что я понял" in t for t in texts(tg))
    assert any("Сделано: список" in t for t in texts(tg))


def test_answers_are_reunderstood_then_task_continues(tmp_path):
    claude = FakeClaude(questions=["Какие теги?"])
    bot, tg, ctl = make(tmp_path, claude)
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    assert ctl.sched.tasks["1"].state is State.WAITING_HUMAN and claude.executed == []
    bot.handle(reply(ctl, "1", "Теги: дом, работа"))
    assert ctl.sched.tasks["1"].state is State.PENDING
    bot.work_once()
    assert claude.understood == 2 and claude.executed == ["1"]


def test_answer_that_makes_task_risky_still_needs_yes(tmp_path):
    claude = FakeClaude(questions=["Кому?"], risky_after_answers=True)
    bot, tg, ctl = make(tmp_path, claude)
    bot.handle(msg("Подготовь письмо"))
    bot.work_once()
    bot.handle(reply(ctl, "1", "Отправь клиенту Муроду"))
    bot.work_once()
    assert ctl.sched.tasks["1"].state is State.WAITING_HUMAN and claude.executed == []


def test_risky_task_needs_explicit_yes_and_no_cancels(tmp_path):
    claude = FakeClaude(needs_owner=True)
    bot, tg, ctl = make(tmp_path, claude)
    bot.handle(msg("Удали старые рендеры"))
    bot.work_once()
    assert ctl.sched.tasks["1"].state is State.WAITING_HUMAN
    bot.handle(reply(ctl, "1", "нет"))
    assert ctl.sched.tasks["1"].state is State.FAILED
    bot.work_once()
    assert claude.executed == []


def test_question_like_reply_is_not_a_yes(tmp_path):
    claude = FakeClaude(needs_owner=True)
    bot, tg, ctl = make(tmp_path, claude)
    bot.handle(msg("Удали старые рендеры"))
    bot.work_once()
    bot.handle(reply(ctl, "1", "Можно ли сначала показать список?"))
    bot.work_once()
    assert claude.executed == []
    bot.handle(reply(ctl, "1", "да"))
    bot.work_once()
    assert claude.executed == ["1"]


def test_failed_run_asks_before_repeating(tmp_path):
    claude = FakeClaude(ok=False)
    bot, tg, ctl = make(tmp_path, claude)
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    bot.work_once()
    assert claude.executed == ["1"]                          # сам с нуля не повторяет
    assert ctl.sched.tasks["1"].state is State.WAITING_HUMAN
    assert any("не получилось" in t.lower() for t in texts(tg))
    claude.ok = True
    bot.handle(reply(ctl, "1", "да"))
    bot.work_once()
    assert claude.executed == ["1", "1"] and ctl.sched.tasks["1"].state is State.DONE


def test_lost_report_does_not_rerun_the_work(tmp_path):
    claude = FakeClaude()
    bot, tg, ctl = make(tmp_path, claude, tg=FakeTG(fail_on="Сделано"))
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    bot.work_once()
    assert claude.executed == ["1"] and ctl.sched.tasks["1"].state is State.DONE


def test_cancel_during_execution_wins(tmp_path):
    bot, tg, ctl = None, None, None

    def cancel_midway(task):
        bot.handle(msg(f"/cancel {task.id}"))

    claude = FakeClaude(on_execute=cancel_midway)
    bot, tg, ctl = make(tmp_path, claude)
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    bot.work_once()
    assert ctl.sched.tasks["1"].state is State.FAILED and claude.executed == ["1"]


def test_interrupted_run_after_restart_asks_before_repeating(tmp_path):
    claude = FakeClaude()
    bot, tg, ctl = make(tmp_path, claude)
    t = ctl.new_task("Сделай список дел")
    t.checkpoint.update(understood=["x"], ready=True, executing=True)   # ПК выключили посреди работы
    bot.work_once()
    assert claude.executed == [] and t.state is State.WAITING_HUMAN
    assert any("прервал" in x for x in texts(tg))


def test_limit_pauses_task_until_later_and_tells_once(tmp_path):
    class Limited(FakeClaude):
        def understand(self, task):
            raise LimitReached("лимит подписки")

    bot, tg, ctl = make(tmp_path, Limited())
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    bot.work_once()
    t = ctl.sched.tasks["1"]
    assert t.state is State.PAUSED and t.checkpoint.get("not_before")
    assert sum("лимит" in x.lower() for x in texts(tg)) == 1


# --- контролёр -------------------------------------------------------------------
def test_controller_alerts_are_sent_and_resent_if_delivery_failed(tmp_path):
    claude = FakeClaude(questions=["Какие теги?"])
    tg = FakeTG()
    bot, tg, ctl = make(tmp_path, claude, tg=tg)
    ctl.escalation_min = 0
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    tg.fail_on = "Срочно"
    bot.check_alerts()
    tg.fail_on = None
    bot.check_alerts()                                         # не потерялась после сбоя отправки
    assert any(t.startswith("Срочно") for t in texts(tg))


# --- исполнитель Claude ----------------------------------------------------------
def test_executor_hides_bot_token_and_env_file_from_claude(monkeypatch, tmp_path):
    import jarviscore.claude_runner as cr

    seen = {}

    def fake_run(prompt, cwd, **kw):
        seen.update(kw)
        return SimpleNamespace(ok=True, result='{"understood": ["a"], "questions": []}')

    monkeypatch.setattr(cr, "run", fake_run)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    ex = ClaudeExecutor({"models": {"developer": "sonnet"}}, root=tmp_path)
    t = Controller(Scheduler(), tmp_path / "t.json").new_task("x")
    ex.understand(t)
    assert "TELEGRAM_BOT_TOKEN" not in seen["env"]
    assert any(".env" in d for d in seen["disallowed_tools"])


def test_executor_raises_limit_on_subscription_limit(monkeypatch, tmp_path):
    import jarviscore.claude_runner as cr

    monkeypatch.setattr(cr, "run", lambda p, c, **kw: SimpleNamespace(ok=False, result="Claude usage limit reached"))
    ex = ClaudeExecutor({"models": {"developer": "sonnet"}}, root=tmp_path)
    t = Controller(Scheduler(), tmp_path / "t.json").new_task("x")
    with pytest.raises(LimitReached):
        ex.understand(t)
