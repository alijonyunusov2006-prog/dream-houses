"""Бот JARVIS в Telegram: личный канал владельца (не бот Qabat).

Голосовое или текст → задача у контролёра → «Вот что я понял» → вопросы владельцу, если они есть,
и «да» на рискованное (деньги, удаление, публикации…) → выполнение через Claude Code → отчёт.
Сообщение «Идея: …» не становится задачей, а записывается во второй мозг (``brain/05-ideas``).

Надёжность: работа с нуля сама не повторяется (сбой, перезапуск ПК → вопрос «повторить?»);
отмена побеждает работающую задачу; лимит подписки → пауза на час, а не круги.

Запуск на ПК: ``Запустить-JARVIS.cmd`` в папке ``jarvis`` (окно + Telegram, см. ``app.py``).
Ключ бота и номер чата владельца — в ``jarvis/.env``: TELEGRAM_BOT_TOKEN, OWNER_CHAT_ID.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .claude_runner import BudgetExceeded
from .controller import Controller
from .planner import State, Task
from . import memory
from .memory import is_recall
from .wake import is_greeting

ROOT = Path(__file__).resolve().parents[2]          # .../jarvis
log = logging.getLogger("jarvis.bot")

HELP = ("Я JARVIS. Пишите или говорите голосовым — я пойму задачу, скажу, что понял, и сделаю.\n"
        "«Идея: …» — запишу во второй мозг.\n"
        "На мои вопросы отвечайте ответом на моё сообщение (свайп влево).\n"
        "/tasks — открытые задачи · /cancel N — отменить задачу №N · /id — номер этого чата")
IDEA = re.compile(r"^\s*(идея|запомни идею)\s*[:,.\-—]?\s*", re.I)
YES = re.compile(r"^\s*(да|ага|делай|давай|ок|ok|хорошо|разрешаю|повтори)(\s*,?\s*(делай|давай|можно))?[\s.!]*$", re.I)
NO = re.compile(r"^\s*(нет|не надо|отмена|стоп|не делай)\b", re.I)
LIMIT_PAUSE_MIN = 60
SECRET_ENV = ("TELEGRAM_BOT_TOKEN",)


class LimitReached(RuntimeError):
    """Лимит подписки Claude или дневной порог — ждать, а не повторять."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JarvisBot:
    def __init__(self, tg, ctl: Controller, claude, stt, *, owner_chat: int | None,
                 ideas_dir: Path = ROOT / "brain" / "05-ideas", tmp_dir: Path = ROOT / "data" / "tmp"):
        self.tg, self.ctl, self.claude, self.stt = tg, ctl, claude, stt
        self.owner, self.ideas_dir, self.tmp_dir = owner_chat, Path(ideas_dir), Path(tmp_dir)
        self.lock = threading.RLock()
        self.report_hour = 8                       # утренний доклад (settings.toml [telegram] report_hour)
        self.memory_roots = [self.ideas_dir.parent]  # где искать «вспомни…»: brain/ (+ хранилище Obsidian из app.py)

    # --- входящие ----------------------------------------------------------------
    def handle(self, update: dict) -> None:
        msg = update.get("message")
        if not msg or msg.get("from", {}).get("is_bot"):
            return
        chat = msg["chat"]["id"]
        text = (msg.get("text") or msg.get("caption") or "").strip()
        if text.startswith("/id") and (self.owner is None or chat == self.owner):
            self.tg.send(chat, f"Номер этого чата: {chat}. Впишите его в jarvis/.env как OWNER_CHAT_ID.")
            return
        if self.owner is None or chat != self.owner:
            return                                  # чужие сообщения — молча мимо
        source = "text"
        audio = msg.get("voice") or msg.get("audio")
        if audio:
            text = self._transcribe(audio["file_id"], msg["message_id"])
            source = "voice"
        if not text:
            return
        with self.lock:
            self._route(msg, text, source)
            self.ctl.save()

    def _transcribe(self, file_id: str, mid: int) -> str:
        try:
            self.tmp_dir.mkdir(parents=True, exist_ok=True)
            path = self.tg.download(file_id, self.tmp_dir / f"voice-{mid}.ogg")
            text = self.stt.transcribe(path)
            path.unlink(missing_ok=True)
        except Exception as e:
            log.exception("голосовое не расшифровано")
            self.tg.send(self.owner, f"Не смог расшифровать голосовое: {e}. Напишите текстом, пожалуйста.")
            return ""
        self.tg.send(self.owner, f"🎙 Расслышал: {text or '(тишина)'}", reply_to=mid)
        return text

    def _route(self, msg: dict, text: str, source: str) -> None:
        reply_to = (msg.get("reply_to_message") or {}).get("message_id")
        waiting = self.ctl.waiting_for_reply_to(reply_to) if reply_to else None
        if waiting:
            return self._on_answer(waiting, text)
        if text in ("/start", "/help"):
            return self.tg.send(self.owner, HELP)
        if text.startswith("/tasks"):
            return self.tg.send(self.owner, self.ctl.summary())
        if text.startswith("/cancel"):
            return self._cancel(text.removeprefix("/cancel").strip())
        if is_recall(text):
            return self.tg.send(self.owner, memory.answer(text, self.memory_roots))
        if is_greeting(text):
            return self.tg.send(self.owner, self.briefing())
        if IDEA.match(text):
            return self._save_idea(IDEA.sub("", text, count=1), source)
        t = self.ctl.new_task(text, source=source)
        self.tg.send(self.owner, f"Принял, задача №{t.id}. Сейчас пришлю, что понял.")

    def _on_answer(self, t: Task, text: str) -> None:
        kind = t.checkpoint.get("confirm")
        if kind and NO.match(text):
            self._stop(t, "отменено владельцем")
            self.tg.send(self.owner, f"Понял, задачу №{t.id} не делаю.")
            return
        self.ctl.answer(t.id, text)
        t.checkpoint.pop("confirm", None)
        if kind and YES.match(text):
            if kind == "risky":
                t.checkpoint["approved"] = True
            # «да» на повтор или риск: если уже понято — сразу к делу, иначе понять заново
            t.checkpoint["ready"] = bool(t.checkpoint.get("understood"))
        else:
            # ответ на вопросы или уточнение вместо «да» — понять заново: ответ может сделать задачу рискованной
            t.checkpoint["ready"] = False
        self.tg.send(self.owner, f"Принял ответ по задаче №{t.id}, продолжаю.")

    def maybe_morning(self, now: datetime | None = None) -> bool:
        """Утренний доклад один раз в день, после часа ``report_hour`` (ПК включили позже — придёт при включении)."""
        now = now or datetime.now()
        mark = self.tmp_dir.parent / "morning.txt"
        if now.hour < self.report_hour or (mark.exists() and mark.read_text().strip() == now.date().isoformat()):
            return False
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text(now.date().isoformat())
        self.tg.send(self.owner, "Утренний доклад.\n" + self.briefing(now))
        return True

    def briefing(self, now: datetime | None = None) -> str:
        """Доклад в манере дворецкого: «я дома», «привет», утренний отчёт. Без Claude — мгновенно и бесплатно."""
        now = now or datetime.now()
        h = now.hour
        hello = ("Доброй ночи, сэр. Снова работаем допоздна?" if h < 5 or h >= 23 else
                 "Доброе утро, сэр." if h < 12 else "Добрый день, сэр." if h < 18 else "Добрый вечер, сэр.")
        tasks = list(self.ctl.sched.tasks.values())
        waiting = [t for t in tasks if t.state is State.WAITING_HUMAN]
        running = [t for t in tasks if t.state is State.RUNNING]
        queued = [t for t in tasks if t.state in (State.PENDING, State.PAUSED, State.BLOCKED)]
        done_today = [t for t in tasks if t.state is State.DONE and t.updated_at.astimezone().date() == now.date()]
        lines = [hello]
        if waiting:
            lines.append("Ждут вашего решения: " + "; ".join(f"№{t.id} «{t.title}»" for t in waiting) + ".")
        if running:
            lines.append("В работе: " + "; ".join(f"№{t.id} «{t.title}»" for t in running) + ".")
        if queued:
            lines.append(f"Ещё {len(queued)} в очереди.")
        if done_today:
            lines.append(f"Сегодня сделано: {len(done_today)}.")
        ideas = self.ideas_dir / f"{now.date().isoformat()}-telegram.md"
        if ideas.exists():
            n = sum(1 for line in ideas.read_text(encoding="utf-8").splitlines() if line.startswith("- "))
            lines.append(f"Записано идей за сегодня: {n}.")
        if len(lines) == 1:
            lines.append("Всё спокойно: задач нет. Чем займёмся?")
        elif waiting:
            lines.append("Начнём с ответа?")
        return "\n".join(lines)

    def _stop(self, t: Task, why: str) -> None:
        t.state, t.progress = State.FAILED, why
        t.checkpoint["cancelled"] = True
        t.touch()

    def _cancel(self, num: str) -> None:
        t = self.ctl.sched.tasks.get(num)
        if not t or t.state in (State.DONE, State.FAILED):
            self.tg.send(self.owner, f"Открытой задачи №{num} нет. /tasks — список.")
            return
        self._stop(t, "отменено владельцем")
        self.tg.send(self.owner, f"Задача №{num} отменена.")

    def _save_idea(self, idea: str, source: str) -> None:
        self.ideas_dir.mkdir(parents=True, exist_ok=True)
        path = self.ideas_dir / f"{date.today().isoformat()}-telegram.md"
        head = "" if path.exists() else f"# Идеи из Telegram — {date.today().isoformat()}\n\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{head}- {datetime.now():%H:%M} ({'голос' if source == 'voice' else 'текст'}): {idea}\n")
        self.tg.send(self.owner, "💡 Записал идею во второй мозг. Утром разберу и предложу, что с ней сделать.")

    # --- контролёр (свой поток, не ждёт исполнителя) ------------------------------
    def check_alerts(self) -> None:
        with self.lock:
            for a in self.ctl.check():
                try:
                    self.tg.send(self.owner, a.text)
                except Exception:
                    log.exception("тревога не ушла")
                    self.ctl.unmark(a)              # повторить при следующей проверке
            self.ctl.save()
            try:
                self.maybe_morning()
            except Exception:
                log.exception("утренний доклад")

    # --- исполнитель --------------------------------------------------------------
    def _next(self) -> Task | None:
        now = _now()
        for t in self.ctl.sched.runnable():
            nb = t.checkpoint.get("not_before")
            if not t.checkpoint.get("cancelled") and (not nb or datetime.fromisoformat(nb) <= now):
                return self.ctl.sched.start(t.id)
        return None

    def work_once(self) -> None:
        """Один шаг исполнителя: одна задача из очереди."""
        with self.lock:
            task = self._next()
            self.ctl.save()
        if task:
            self._advance(task)
            with self.lock:
                self.ctl.save()

    def _live(self, t: Task) -> bool:
        return not t.checkpoint.get("cancelled") and t.state not in (State.DONE, State.FAILED)

    def _advance(self, t: Task) -> None:
        try:
            if t.checkpoint.pop("executing", False):     # прошлый запуск оборвался (выключение, сбой)
                with self.lock:
                    self._ask_yes(t, "retry", "прошлый запуск прервался посередине, часть работы могла быть сделана. "
                                              "Повторить с начала?")
                return
            if not t.checkpoint.get("ready"):
                self._understand(t)
            if t.checkpoint.get("ready") and self._live(t):
                self._execute(t)
        except (LimitReached, BudgetExceeded) as e:
            with self.lock:
                self._pause_for_limit(t, str(e))
        except Exception as e:
            log.exception("задача %s", t.id)
            with self.lock:
                if self._live(t):
                    self._ask_yes(t, "retry", f"не получилось — {str(e)[:300]}. Повторить?")

    def _pause_for_limit(self, t: Task, why: str) -> None:
        if not self._live(t):
            return
        t.state = State.PAUSED
        t.checkpoint["not_before"] = (_now() + timedelta(minutes=LIMIT_PAUSE_MIN)).isoformat()
        t.touch()
        self.tg.send(self.owner, f"Задача №{t.id} на паузе: упёрся в лимит ({why[:200]}). "
                                 f"Продолжу сам через {LIMIT_PAUSE_MIN} мин.")

    def _understand(self, t: Task) -> None:
        info = self.claude.understand(t)
        with self.lock:
            if not self._live(t):
                return
            t.checkpoint["understood"] = info.get("understood", [])
            t.checkpoint.update(needs_owner=bool(info.get("needs_owner")), reason=info.get("reason") or "")
            points = "\n".join(f"• {p}" for p in t.checkpoint["understood"]) or "• (пусто)"
            self.tg.send(self.owner, f"Вот что я понял (№{t.id}):\n{points}")
            questions = info.get("questions") or []
            if questions:
                q = "\n".join(f"{i}. {x}" for i, x in enumerate(questions, 1))
                sent = self.tg.send(self.owner, f"Вопросы по №{t.id} — ответьте на это сообщение:\n{q}")
                self.ctl.ask(t.id, q, ask_msg=sent.get("message_id"))
            elif t.checkpoint["needs_owner"] and not t.checkpoint.get("approved"):
                why = t.checkpoint["reason"] or "это из списка «всегда спрашивать»"
                self._ask_yes(t, "risky", f"требует вашего «да»: {why}\nДелать?")
            else:
                t.checkpoint["ready"] = True

    def _ask_yes(self, t: Task, kind: str, text: str) -> None:
        sent = self.tg.send(self.owner, f"№{t.id} {text}\nОтветьте на это сообщение «да» или «нет».")
        self.ctl.ask(t.id, text, ask_msg=sent.get("message_id"))
        t.checkpoint["confirm"] = kind

    def _execute(self, t: Task) -> None:
        with self.lock:
            t.checkpoint["executing"] = True     # если ПК выключат посреди работы — спросим, а не повторим молча
            self.ctl.save()
        res = self.claude.execute(t)
        with self.lock:
            t.checkpoint.pop("executing", None)
            if not self._live(t):
                log.info("задача %s отменена во время работы; результат: %s", t.id, res.result[:300])
                return
            if res.ok:
                self.ctl.sched.complete(t.id, res.result[:2000])
                try:
                    self.tg.send(self.owner, f"Задача №{t.id}:\n{res.result}")
                except Exception:
                    log.exception("отчёт по задаче %s не ушёл (работа сделана, в progress)", t.id)
            elif _is_limit(res.result):
                self._pause_for_limit(t, res.result)
            else:
                t.checkpoint["ready"] = True
                self._ask_yes(t, "retry", f"не получилось.\n{res.result[:1500]}\nПовторить?")


def _is_limit(text: str) -> bool:
    return bool(re.search(r"usage limit|rate limit|limit reached|лимит", text or "", re.I))


class ClaudeExecutor:
    """Исполнитель через Claude Code (``claude -p``) по подписке владельца."""

    UNDERSTAND = (
        "Ты JARVIS. Владелец прислал задание (возможно, голосом — распознавание с ошибками, понимай по смыслу).\n"
        "Ничего не делай, только пойми. Можешь читать файлы. Ответь ТОЛЬКО JSON без пояснений:\n"
        '{{"understood": ["3–7 коротких пунктов простым русским"], "questions": ["только то, без чего нельзя начать"], '
        '"needs_owner": true/false, "reason": "почему нужно «да», если needs_owner"}}\n'
        "needs_owner = true, если задача из brain/10-rules/always-ask.md (деньги, удаление, публикации, сообщения людям, "
        "аккаунты, печать, выключение ПК, CRM).\n\nЗадание:\n{text}{answers}"
    )
    EXECUTE = (
        "Ты JARVIS. Выполни задание владельца полностью, по правилам CLAUDE.md и brain/10-rules.\n"
        "Что ты понял: {understood}\n\nЗадание:\n{text}{answers}\n\n"
        "В конце — короткий отчёт по-русски: Сделано / Проверено (как) / Нужно решить / Следующий шаг / Файлы. "
        "Не пиши «готово», если не проверил. Пиши простым текстом без разметки: без звёздочек, решёток и таблиц — "
        "ответ читают в Telegram и в окне JARVIS."
    )
    HIDDEN = ["Read(./.env)", "Read(./**/.env)", "Read(.env)"]

    def __init__(self, settings: dict, root: Path = ROOT):
        self.s, self.root = settings, root

    @staticmethod
    def _answers(t: Task) -> str:
        a = t.checkpoint.get("answers") or []
        return ("\n\nОтветы владельца:\n" + "\n".join(f"- {x}" for x in a)) if a else ""

    def _run(self, prompt: str, task_id: str, **kw):
        from . import claude_runner

        env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}   # ключ бота Claude не видит
        res = claude_runner.run(prompt, self.root, task_id=task_id, env=env, disallowed_tools=self.HIDDEN,
                                cost_log=self.root / "data" / "logs" / "costs.jsonl",
                                daily_budget_usd=self.s.get("budget", {}).get("daily_usd_equivalent"), **kw)
        if not res.ok and _is_limit(res.result):
            raise LimitReached(res.result[:200])
        return res

    def understand(self, t: Task) -> dict:
        prompt = self.UNDERSTAND.format(text=t.checkpoint.get("text", t.title), answers=self._answers(t))
        res = self._run(prompt, t.id, model=self.s["models"]["developer"], max_turns=8,
                        permission_mode="plan", allowed_tools=["Read", "Glob", "Grep"], timeout_sec=600)
        if not res.ok:
            raise RuntimeError(f"Claude не смог разобрать задание: {res.result[:300]}")
        m = re.search(r"\{.*\}", res.result, re.S)
        try:
            info = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            info = {}
        if not info:  # не смог разобрать — безопасный путь: показать как есть и спросить «да»
            info = {"understood": [res.result[:500]], "questions": [], "needs_owner": True,
                    "reason": "я не уверен, что правильно понял"}
        return info

    def execute(self, t: Task):
        cc = self.s.get("claude_code", {})
        prompt = self.EXECUTE.format(understood="; ".join(t.checkpoint.get("understood", [])),
                                     text=t.checkpoint.get("text", t.title), answers=self._answers(t))
        return self._run(prompt, t.id, model=self.s["models"]["developer"], max_turns=cc.get("max_turns", 40),
                         permission_mode=cc.get("permission_mode", "acceptEdits"),
                         allowed_tools=cc.get("default_allowed_tools"), timeout_sec=3600)


def load_env(path: Path) -> None:
    """Простейший .env: KEY=VALUE построчно; уже заданные переменные окружения не перезаписываются."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
