"""Окно JARVIS на ПК: маленький веб-сервер только для этого компьютера (127.0.0.1).

Страница ``web/index.html`` — шар-«лицо», переписка, микрофон, задачи. Сервер принимает
сообщения владельца из окна и передаёт их тому же боту, что и Telegram.

Защита: слушает только 127.0.0.1 (из сети не достучаться); принимает запросы только с заголовком
Host этого компьютера (защита от подмены адреса) и POST только с заголовком ``X-Jarvis: 1``
(чужая страница в браузере не сможет отправить команду).
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .controller import STATE_RU
from .planner import State

log = logging.getLogger("jarvis.web")
PAGE = Path(__file__).with_name("web") / "index.html"
MAX_VOICE = 25 * 1024 * 1024


class JarvisWeb:
    """Связка окна с ботом: что пришло из окна → бот; что показать → лента и задачи."""

    def __init__(self, bot, feed, tmp_dir: Path):
        self.bot, self.feed, self.tmp_dir = bot, feed, Path(tmp_dir)
        self._n = 0

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

    def state(self, after: int) -> dict:
        with self.bot.lock:
            tasks = [{"id": t.id, "title": t.title, "state": t.state.value, "state_ru": STATE_RU[t.state],
                      "ask_msg": t.checkpoint.get("ask_msg"), "confirm": t.checkpoint.get("confirm") or ""}
                     for t in self.bot.ctl.open_tasks()]
        busy = any(t["state"] == State.RUNNING.value for t in tasks)
        return {"feed": self.feed.since(after), "tasks": tasks, "busy": busy}


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
