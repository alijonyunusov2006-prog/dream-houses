# Минимальный клиент Telegram Bot API на стандартной библиотеке. Опрос (getUpdates) —
# публичный адрес и туннель для Telegram не нужны, бот работает с любого ПК с интернетом.
import json
import urllib.error
import urllib.parse
import urllib.request


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, timeout: float = 60):
        if not token:
            raise TelegramError("Нет ключа бота: задайте переменную QABAT_TG_BOT_TOKEN")
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
            # ключ в текст ошибки не попадает: в описании только ответ Telegram
            raise TelegramError(f"{method}: {res.get('description', 'ошибка')}")
        return res["result"]

    def get_updates(self, offset: int | None):
        return self.call("getUpdates", offset=offset, timeout=int(self.timeout),
                         allowed_updates=["message"])

    def send(self, chat_id, text, thread_id=None):
        return self.call("sendMessage", chat_id=chat_id, text=text, message_thread_id=thread_id)

    def copy(self, to_chat, from_chat, message_id, thread_id=None):
        return self.call("copyMessage", chat_id=to_chat, from_chat_id=from_chat,
                         message_id=message_id, message_thread_id=thread_id)

    def create_topic(self, chat_id, name):
        return self.call("createForumTopic", chat_id=chat_id, name=name[:128])["message_thread_id"]
