"""Окно JARVIS на ПК: маленький веб-сервер только для этого компьютера (127.0.0.1).

Страница ``web/index.html`` — шар-«лицо», переписка, микрофон, задачи. Сервер принимает
сообщения владельца из окна и передаёт их тому же боту, что и Telegram.

Защита: слушает только 127.0.0.1 (из сети не достучаться); принимает запросы только с заголовком
Host этого компьютера (защита от подмены адреса) и POST только с заголовком ``X-Jarvis: 1``
(чужая страница в браузере не сможет отправить команду).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.request
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .controller import STATE_RU
from .planner import State
from .wake import find_wake

log = logging.getLogger("jarvis.web")
PAGE = Path(__file__).with_name("web") / "index.html"
MAX_VOICE = 25 * 1024 * 1024


class JarvisWeb:
    """Связка окна с ботом: что пришло из окна → бот; что показать → лента и задачи."""

    ARMED_SEC = 6           # позвали без команды («Джарвис!») — столько секунд ждём команду без имени (коротко: чтобы ТВ рядом не стал командой)

    def __init__(self, bot, feed, tmp_dir: Path):
        self.bot, self.feed, self.tmp_dir = bot, feed, Path(tmp_dir)
        self._n = 0
        self._armed_until = 0.0
        self._hear_lock = threading.Lock()
        self.tts_url = "http://127.0.0.1:8766"
        self.on_pill = None                      # app.py подставляет открытие окна «сверху»

    def hear(self, audio: bytes, now: float | None = None) -> dict:
        """Фраза из режима «слушать «Джарвис»». Без зова — выбрасываем, нигде не сохраняя."""
        now = time.monotonic() if now is None else now
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        with self._hear_lock:
            self._n += 1
            path = self.tmp_dir / f"hear-{self._n}.wav"
            path.write_bytes(audio)
            try:
                text = self.bot.stt.transcribe(path)
            finally:
                path.unlink(missing_ok=True)
        found, command = find_wake(text)
        if not found and now < self._armed_until and text.strip():
            found, command = True, text.strip()
        if not found:
            return {"heard": False}
        if not command:
            self.bot.tg.send(self.bot.owner, "Слушаю, сэр.")
            self._armed_until = now + self.ARMED_SEC
            return {"heard": True, "armed": True}
        self._armed_until = 0.0
        self.send_text(command, None)
        return {"heard": True, "text": command}

    def _message(self, mid: int, text: str = "", reply_to: int | None = None, voice: str = "") -> dict:
        m = {"message_id": mid, "chat": {"id": self.bot.owner, "type": "private"},
             "from": {"id": self.bot.owner, "is_bot": False}}
        if text:
            m["text"] = text
        if reply_to:
            m["reply_to_message"] = {"message_id": reply_to}
        if voice:
            m["voice"] = {"file_id": "web:" + voice}
        return {"update_id": 0, "message": m}

    def send_text(self, text: str, reply_to: int | None) -> int:
        mid = self.feed.add_owner(text, reply_to)
        self.bot.handle(self._message(mid, text, reply_to))
        return mid

    def send_voice(self, audio: bytes, reply_to: int | None) -> int:
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._n += 1
        path = self.tmp_dir / f"web-voice-{self._n}.webm"
        path.write_bytes(audio)
        mid = self.feed.add_owner("🎙 голосовое", reply_to)
        # распознавание может занять десятки секунд (первая загрузка модели) — не держим окно
        threading.Thread(target=self.bot.handle, args=(self._message(mid, reply_to=reply_to, voice=str(path)),),
                         daemon=True).start()
        return mid

    def speech(self, msg_id: int) -> bytes | None:
        """Ответ JARVIS его голосом: служба голоса на ПК (golos/jarvis_tts_server.py). Озвученное — в кэш."""
        item = next((m for m in self.feed.since(msg_id - 1) if m["id"] == msg_id and m["who"] == "jarvis"), None)
        if not item:
            return None
        text = item["text"]
        cache = self.tmp_dir.parent / "tts" / (hashlib.sha1(text.encode("utf-8")).hexdigest()[:16] + ".wav")
        if cache.exists():
            return cache.read_bytes()
        req = urllib.request.Request(self.tts_url + "/speak", data=json.dumps({"text": text}).encode("utf-8"),
                                     headers={"X-Jarvis": "1", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                audio = r.read()
        except Exception:
            log.warning("служба голоса недоступна — окно прочитает голосом браузера")
            return None
        cache.parent.mkdir(parents=True, exist_ok=True)
        part = cache.with_name(f"{cache.stem}.{threading.get_ident()}.part")
        part.write_bytes(audio)
        os.replace(part, cache)                 # атомарно: недописанный звук никто не получит
        return audio

    def state(self, after: int) -> dict:
        today = datetime.now().astimezone().date()
        with self.bot.lock:
            tasks = [{"id": t.id, "title": t.title, "state": t.state.value, "state_ru": STATE_RU[t.state],
                      "ask_msg": t.checkpoint.get("ask_msg"), "confirm": t.checkpoint.get("confirm") or "",
                      "stage": stage(t)}
                     for t in self.bot.ctl.open_tasks()]
            done_today = sum(1 for t in self.bot.ctl.sched.tasks.values()
                             if t.state is State.DONE and t.updated_at.astimezone().date() == today)
        busy = any(t["state"] == State.RUNNING.value for t in tasks)
        stats = {"open": len(tasks), "waiting": sum(t["state"] == State.WAITING_HUMAN.value for t in tasks),
                 "running": sum(t["state"] == State.RUNNING.value for t in tasks), "done_today": done_today}
        return {"feed": self.feed.since(after), "tasks": tasks, "busy": busy, "stats": stats}


STAGES = ["принял", "понимаю", "делаю", "проверка", "отчёт"]


def stage(t) -> int:
    """На каком шаге конвейера задача: 0 принял · 1 понимаю · 2 делаю (· 3–4 — после выполнения)."""
    if t.state is State.RUNNING:
        return 2 if t.checkpoint.get("ready") else 1
    if t.state is State.WAITING_HUMAN:
        return 1
    return 0


def make_handler(app: JarvisWeb, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # без шума в консоли; ошибки — в журнал
            log.debug(fmt, *args)

        def _reply(self, code: int, body: bytes = b"", ctype: str = "application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                             "font-src https://fonts.gstatic.com; connect-src 'self'; media-src 'self' blob:; "
                             "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, data) -> None:
            self._reply(code, json.dumps(data, ensure_ascii=False).encode())

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def do_GET(self):
            if not self._host_ok():
                return self._json(403, {"error": "чужой адрес"})
            url = urlparse(self.path)
            if url.path == "/":
                return self._reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            m = re.fullmatch(r"/([a-z]+)\.js", url.path)            # только скрипты окна, без папок и «..»
            if m and (PAGE.parent / f"{m.group(1)}.js").is_file():
                return self._reply(200, (PAGE.parent / f"{m.group(1)}.js").read_bytes(),
                                   "application/javascript; charset=utf-8")
            if url.path == "/api/tts":
                mid = (parse_qs(url.query).get("id") or ["0"])[0]
                audio = app.speech(int(mid)) if mid.isdigit() else None
                return self._reply(200, audio, "audio/wav") if audio else self._json(503, {"error": "голос недоступен"})
            if url.path == "/api/state":
                after = int((parse_qs(url.query).get("after") or ["0"])[0] or 0)
                return self._json(200, app.state(after))
            self._json(404, {"error": "нет такой страницы"})

        def do_POST(self):
            if not self._host_ok() or self.headers.get("X-Jarvis") != "1":
                return self._json(403, {"error": "запрещено"})
            size = int(self.headers.get("Content-Length") or 0)
            if size > MAX_VOICE:
                return self._json(413, {"error": "слишком большой файл"})
            body = self.rfile.read(size)
            url = urlparse(self.path)
            try:
                if url.path == "/api/send":
                    data = json.loads(body or b"{}")
                    text = str(data.get("text", "")).strip()[:8000]
                    if not text:
                        return self._json(400, {"error": "пустое сообщение"})
                    return self._json(200, {"id": app.send_text(text, data.get("reply_to"))})
                if url.path == "/api/pill":
                    if app.on_pill:
                        app.on_pill()
                    return self._json(200, {"ok": bool(app.on_pill)})
                if url.path == "/api/hear":
                    if not body:
                        return self._json(400, {"error": "пустая запись"})
                    return self._json(200, app.hear(body))
                if url.path == "/api/voice":
                    if not body:
                        return self._json(400, {"error": "пустая запись"})
                    reply_to = parse_qs(url.query).get("reply_to", [None])[0]
                    return self._json(202, {"id": app.send_voice(body, int(reply_to) if reply_to else None)})
            except Exception:
                log.exception("окно: %s", url.path)
                return self._json(500, {"error": "ошибка на стороне JARVIS, смотрите data/logs/bot.log"})
            self._json(404, {"error": "нет такого действия"})

    return Handler


def serve(app: JarvisWeb, port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, port))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
