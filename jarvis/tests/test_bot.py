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
    assert "В очереди: 1" in text and "Сделано сегодня, 1: «Старое»" in text


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


def test_morning_report_retried_if_sending_failed(tmp_path):
    bot, tg, ctl = make(tmp_path, tg=FakeTG(fail_on="Утренний"))
    with pytest.raises(ConnectionError):
        bot.maybe_morning(datetime(2026, 10, 20, 8, 5))
    bot.tg.fail_on = None
    assert bot.maybe_morning(datetime(2026, 10, 20, 8, 6))               # не потерялся


def test_typed_greeting_with_name_is_briefing_too(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Джарвис, я дома"))
    assert "сэр" in tg.sent[-1][1] and ctl.sched.tasks == {}


def test_typed_task_with_name_strips_the_name(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Джарвис, сделай список дел"))
    assert ctl.sched.tasks["1"].title == "сделай список дел"


def test_simple_question_answered_locally_without_task(tmp_path):
    from jarviscore.local import LocalBrain

    class Fake:
        def reply(self, system, history): return "Будет 96, сэр."
    bot, tg, ctl = make(tmp_path)
    bot.local = LocalBrain(Fake())
    bot.handle(msg("Сколько будет 12 умножить на 8?"))
    assert tg.sent[-1][1] == "Будет 96, сэр." and ctl.sched.tasks == {}


def test_simple_question_falls_back_to_task_when_local_is_down(tmp_path):
    from jarviscore.local import LocalBrain

    class Down:
        def reply(self, system, history): return None
    bot, tg, ctl = make(tmp_path)
    bot.local = LocalBrain(Down())
    bot.handle(msg("Сколько будет 12 умножить на 8?"))
    assert "1" in ctl.sched.tasks


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


class AgentClaude(FakeClaude):
    """Разбор, который выбирает исполнителя."""
    def __init__(self, agent, **kw):
        super().__init__(**kw)
        self.agent = agent

    def agents(self):
        return ["archviz", "developer", "secretary"]

    def understand(self, task):
        info = super().understand(task)
        info["agent"] = self.agent
        return info


def test_understand_assigns_known_agent_and_names_it_in_russian(tmp_path):
    bot, tg, ctl = make(tmp_path, claude=AgentClaude("ArchViz "))
    bot.handle(msg("Сделай рендер гостиной"))
    bot.work_once()
    t = ctl.sched.tasks["1"]
    assert t.checkpoint["agent"] == "archviz"
    assert any("Делает: 3D-визуализатор" in s[1] for s in tg.sent)


def test_understand_rejects_made_up_agent(tmp_path):
    bot, tg, ctl = make(tmp_path, claude=AgentClaude("superman"))
    bot.handle(msg("Сделай что-нибудь"))
    bot.work_once()
    assert ctl.sched.tasks["1"].checkpoint["agent"] == "jarvis"
    assert not any("Делает:" in s[1] for s in tg.sent)


# --- разговор без задач (2026-10-21: «ты здесь?», «Конец.», «не надо, номер 14» становились задачами) ---
def test_presence_answers_without_task(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Джарвис, ты здесь?"))
    assert "сэр" in tg.sent[-1][1] and ctl.sched.tasks == {}


def test_single_word_noise_is_not_a_task(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Конец."))
    assert ctl.sched.tasks == {} and "Не понял" in tg.sent[-1][1]


def test_repeat_says_last_reply_again(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("я дома"))
    first = tg.sent[-1][1]
    bot.handle(msg("повтори"))
    assert tg.sent[-1][1] == first and ctl.sched.tasks == {}


def test_stop_with_number_cancels_that_task(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Сделай список дел"))
    bot.handle(msg("Не надо, номер 1, слушай меня"))
    assert ctl.sched.tasks["1"].checkpoint.get("cancelled") and "№1" in tg.sent[-1][1]


def test_stop_without_number_cancels_latest_open(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Сделай список дел"))
    bot.handle(msg("Сделай второй список"))
    bot.handle(msg("стоп"))
    assert ctl.sched.tasks["2"].checkpoint.get("cancelled") and not ctl.sched.tasks["1"].checkpoint.get("cancelled")


def test_stop_with_nothing_open(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("не надо"))
    assert ctl.sched.tasks == {} and "ничего" in tg.sent[-1][1]


def test_question_gets_short_answer_without_report_ceremony(tmp_path):
    class Q(FakeClaude):
        def ask(self, task):
            return SimpleNamespace(ok=True, result="В папке 4 файла, сэр.", session_id="s")
    bot, tg, ctl = make(tmp_path, claude=Q())
    bot.handle(msg("Сколько файлов в папке образцы?"))
    assert not any("Принял, задача" in s[1] for s in tg.sent)
    bot.work_once()
    assert tg.sent[-1][1] == "В папке 4 файла, сэр."
    assert not any("Вот что я понял" in s[1] for s in tg.sent)
    assert ctl.sched.tasks["1"].state.value == "done"


def test_session_limit_is_russian_pauses_all_and_resumes_at_reset(tmp_path):
    from jarviscore.bot import LimitReached, limit_until

    class Limited(FakeClaude):
        def understand(self, task):
            raise LimitReached("You've hit your session limit · resets 10:10pm (Asia/Dushanbe)")
    bot, tg, ctl = make(tmp_path, claude=Limited())
    bot.handle(msg("Сделай список дел"))
    bot.handle(msg("Сделай второй список"))
    bot.work_once()
    text = tg.sent[-1][1]
    assert "22:10" in text and "limit" not in text.lower() and "лимит" in text
    n = len(tg.sent)
    bot.work_once()                                    # вторую задачу не трогаем до сброса и не пишем снова
    assert len(tg.sent) == n and ctl.sched.tasks["2"].state.value == "pending"
    assert "22:10" in bot.briefing()
    u = limit_until("resets 10:10pm (Asia/Dushanbe)").astimezone()
    assert (u.hour, u.minute) == (22, 10)


def test_briefing_names_what_was_done(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Сделай список дел"))
    bot.work_once(); bot.work_once()
    b = bot.briefing()
    assert "список дел" in b.lower() and "Сделано сегодня" in b


def test_show_office_by_voice(tmp_path):
    bot, tg, ctl = make(tmp_path)
    opened = []
    bot.on_office = lambda: opened.append(1)
    bot.handle(msg("Джарвис, покажи офис"))
    assert opened and "офис" in tg.sent[-1][1] and ctl.sched.tasks == {}


def test_limit_until_variants():
    from jarviscore.bot import limit_until
    now = datetime(2026, 10, 21, 20, 0).astimezone()
    loc = lambda s: limit_until(s, now).astimezone()
    assert (loc("resets 12am").hour, loc("resets 12am").day) == (0, 22)
    assert loc("resets 10pm").hour == 22 and loc("resets 22:30").minute == 30
    assert (loc("resets 25 Oct") - now).total_seconds() == 3600          # не время → через час
    assert loc("resets 7:55pm").day == 21 and loc("resets 7:55pm").hour == 20   # только что прошло → почти сразу


def test_limit_during_execute_resumes_without_retry_question(tmp_path):
    from jarviscore.bot import LimitReached

    class Lim(FakeClaude):
        def __init__(self):
            super().__init__(); self.n = 0
        def execute(self, task):
            self.n += 1
            if self.n == 1:
                raise LimitReached("You've hit your session limit · resets 10:10pm")
            return super().execute(task)
    bot, tg, ctl = make(tmp_path, claude=Lim())
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    t = ctl.sched.tasks["1"]
    assert "executing" not in t.checkpoint and t.state.value == "paused"
    bot.paused_until = None; t.checkpoint.pop("not_before")      # «сброс наступил»
    bot.work_once()
    assert t.state.value == "done" and not any("Повторить" in s[1] for s in tg.sent)


def test_cancel_all_and_hush(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("Сделай список дел")); bot.handle(msg("Сделай второй список"))
    bot.handle(msg("отмени всё"))
    assert all(t.checkpoint.get("cancelled") for t in ctl.sched.tasks.values()) and "2" in tg.sent[-1][1]
    bot.handle(msg("замолчи"))
    assert len(ctl.sched.tasks) == 2 and "Молчу" in tg.sent[-1][1]


def test_rude_is_answered_calmly_without_task(tmp_path):
    bot, tg, ctl = make(tmp_path)
    bot.handle(msg("ты тупой"))
    assert ctl.sched.tasks == {} and "сэр" in tg.sent[-1][1]


def test_work_during_limit_is_honest(tmp_path):
    from datetime import timedelta
    from jarviscore.bot import _now
    bot, tg, ctl = make(tmp_path)
    bot.paused_until = _now() + timedelta(hours=1)
    bot.handle(msg("Сделай список дел"))
    text = tg.sent[-1][1]
    assert "№1" in text and "лимит" in text.lower() and "начну" in text


# --- 21.10.2026: Клод Код вышел из аккаунта — №24…№28 «не получилось… Повторить?» с английской ошибкой ---
class AuthDown(FakeClaude):
    def understand(self, task):
        from jarviscore.bot import AuthRequired
        raise AuthRequired("Failed to authenticate: OAuth session expired and could not be refreshed")


def test_logged_out_claude_is_said_once_in_russian_and_tasks_wait(tmp_path):
    bot, tg, ctl = make(tmp_path, claude=AuthDown())
    bot.auth_ok = lambda: False
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    said = [s[1] for s in tg.sent]
    assert any("вышел из аккаунта" in s for s in said)
    assert not any("Повторить" in s or "Failed" in s for s in said)
    assert ctl.sched.tasks["1"].state.value in ("pending", "paused")
    n = len(tg.sent)
    bot.handle(msg("Сделай второй список"))
    assert "вышел из аккаунта" in tg.sent[-1][1] and "№2" in tg.sent[-1][1]
    bot.work_once(); bot.work_once()
    assert len(tg.sent) == n + 1                       # никаких новых «не получилось»


def test_after_login_tasks_continue_by_themselves(tmp_path):
    claude = AuthDown()
    bot, tg, ctl = make(tmp_path, claude=claude)
    bot.auth_ok = lambda: False
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    claude.understand = FakeClaude.understand.__get__(claude)   # вошли — Клод снова работает
    bot.auth_ok = lambda: True
    bot._auth_checked_at = None
    bot.work_once(); bot.work_once()
    assert ctl.sched.tasks["1"].state.value == "done"
    assert any("Вход восстановлен" in s[1] for s in tg.sent)


def test_bare_yes_answers_the_only_waiting_question(tmp_path):
    bot, tg, ctl = make(tmp_path, claude=FakeClaude(needs_owner=True))
    bot.handle(msg("Удали старые рендеры"))
    bot.work_once()
    assert ctl.sched.tasks["1"].state.value == "waiting_human"
    bot.handle(msg("да"))                               # без ответа на сообщение
    assert ctl.sched.tasks["1"].checkpoint.get("approved") and len(ctl.sched.tasks) == 1


def test_talking_about_task_number_answers_that_task(tmp_path):
    bot, tg, ctl = make(tmp_path, claude=FakeClaude(questions=["Какие теги?"]))
    bot.handle(msg("Сделай список дел"))
    bot.work_once()
    bot.handle(msg("Я про первое задание — теги нужны по проектам, задание номер 1"))
    assert len(ctl.sched.tasks) == 1 and "по проектам" in " ".join(ctl.sched.tasks["1"].checkpoint.get("answers", []))
