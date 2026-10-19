"""Каналы связи JARVIS с владельцем: окно на ПК и Telegram — две двери в один дом.

``WebFeed`` — лента сообщений окна JARVIS (хранится в ``data/feed.jsonl``, переживает перезапуск).
``Broadcast`` — то, что бот считает своим «телеграмом»: пишет в окно и, если настроен, в Telegram.
Номера сообщений — номера ленты окна; соответствие с номерами Telegram держит ``Broadcast``,
поэтому ответ на вопрос работает и из окна, и из Telegram.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path

log = logging.getLogger("jarvis.channels")
KEEP = 500          # сколько последних сообщений держать в памяти окна


class WebFeed:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.lock = threading.Lock()
        self.items: list[dict] = []
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines()[-KEEP:]:
                try:
                    self.items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    def _add(self, who: str, text: str, reply_to: int | None) -> int:
        with self.lock:
            mid = (self.items[-1]["id"] + 1) if self.items else 1
            item = {"id": mid, "who": who, "text": text, "reply_to": reply_to,
                    "ts": datetime.now().strftime("%H:%M")}
            self.items.append(item)
            del self.items[:-KEEP]
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            return mid

    def send(self, chat_id, text: str, reply_to: int | None = None) -> dict:
        return {"message_id": self._add("jarvis", text, reply_to)}

    def add_owner(self, text: str, reply_to: int | None = None) -> int:
        return self._add("owner", text, reply_to)

    def since(self, after: int) -> list[dict]:
        with self.lock:
            return [dict(i) for i in self.items if i["id"] > after]


class Broadcast:
    def __init__(self, web: WebFeed, tg=None, tg_chat: int | None = None):
        self.web, self.tg, self.tg_chat = web, tg, tg_chat
        self._web_to_tg: dict[int, int] = {}
        self._tg_to_web: dict[int, int] = {}
        self.lock = threading.Lock()

    def link(self, web_id: int, tg_id: int) -> None:
        with self.lock:
            self._web_to_tg[web_id], self._tg_to_web[tg_id] = tg_id, web_id

    def web_of(self, tg_id: int | None) -> int | None:
        return self._tg_to_web.get(tg_id) if tg_id is not None else None

    def send(self, chat_id, text: str, reply_to: int | None = None) -> dict:
        res = self.web.send(chat_id, text, reply_to)
        if self.tg and self.tg_chat:
            try:
                sent = self.tg.send(self.tg_chat, text, reply_to=self._web_to_tg.get(reply_to))
                if sent.get("message_id"):
                    self.link(res["message_id"], sent["message_id"])
            except Exception:
                log.exception("в Telegram не ушло — в окне сообщение есть")
        return res

    def download(self, file_id: str, dest: Path) -> Path:
        """Голосовое: из окна — локальный файл ``web:<путь>``, из Telegram — скачать."""
        if file_id.startswith("web:"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(file_id[4:], dest)
            return dest
        return self.tg.download(file_id, dest)
