"""Минимальный клиент Telegram Bot API на стандартной библиотеке (как у бота Qabat).

Опрос ``getUpdates``: публичный адрес и облако не нужны. Пока ПК выключен, Telegram хранит
сообщения до 24 часов — после включения бот их заберёт.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

LIMIT = 4000  # Telegram режет сообщения длиннее 4096 символов


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, timeout: float = 50):
        if not token:
            raise TelegramError("Нет ключа бота: впишите TELEGRAM_BOT_TOKEN в jarvis/.env")
        self._token = token
        self._base = f"https://api.telegram.org/bot{token}/"
        self.timeout = timeout

    def call(self, method: str, **params):
        data = urllib.parse.urlencode({k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                                       for k, v in params.items() if v is not None}).encode()
        try:
            with urllib.request.urlopen(self._base + method, data=data, timeout=self.timeout + 10) as r:
                res = json.loads(r.read())
        except urllib.error.HTTPError as e:
            res = json.loads(e.read() or b"{}")
        if not res.get("ok"):
            # ключ в текст ошибки не попадает: только описание от Telegram
            raise TelegramError(f"{method}: {res.get('description', 'ошибка')}")
        return res["result"]

    def get_updates(self, offset: int | None):
        return self.call("getUpdates", offset=offset, timeout=int(self.timeout), allowed_updates=["message"])

    def send(self, chat_id, text: str, reply_to: int | None = None) -> dict:
        text = text or "…"
        last = {}
        for i in range(0, len(text), LIMIT):
            last = self.call("sendMessage", chat_id=chat_id, text=text[i:i + LIMIT],
                             reply_to_message_id=reply_to if i == 0 else None)
        return last

    def send_voice(self, chat_id, ogg: bytes, reply_to: int | None = None) -> dict:
        """Голосовое JARVIS (OGG/Opus) — файл отправляется формой multipart, как требует Telegram."""
        boundary = "jarvis" + uuid.uuid4().hex
        parts = []
        fields = {"chat_id": str(chat_id)}
        if reply_to:
            fields["reply_to_message_id"] = str(reply_to)
        for k, v in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="voice"; filename="jarvis.ogg"\r\n'
                     f"Content-Type: audio/ogg\r\n\r\n".encode() + ogg + b"\r\n")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(self._base + "sendVoice", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout + 30) as r:
                res = json.loads(r.read())
        except urllib.error.HTTPError as e:
            res = json.loads(e.read() or b"{}")
        if not res.get("ok"):
            raise TelegramError(f"sendVoice: {res.get('description', 'ошибка')}")
        return res["result"]

    def download(self, file_id: str, dest: Path) -> Path:
        path = self.call("getFile", file_id=file_id)["file_path"]
        url = f"https://api.telegram.org/file/bot{self._token}/{path}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            dest.write_bytes(r.read())
        return dest
