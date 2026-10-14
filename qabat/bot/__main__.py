# Запуск на ПК:  python -m qabat.bot   (из корня репозитория dream-houses)
# Настройки — переменные окружения (секреты только тут или в .env на ПК, не в Git):
#   QABAT_TG_BOT_TOKEN   ключ бота из BotFather (обязательно)
#   QABAT_OWNER_CHAT_ID  номер группы «Qabat — заявки» с темами; узнать — написать /id в группе
#   QABAT_OLLAMA_URL     по умолчанию http://127.0.0.1:11434
#   QABAT_MODEL / QABAT_MODEL_FAST  по умолчанию [models] local / local_fast из jarvis/config/settings.toml
#   QABAT_DB             файл памяти бота, по умолчанию data/qabat-bot.sqlite рядом с репозиторием
#   QABAT_PRICES         off (по умолчанию) — цены не называть, пока их не утвердил владелец
import os
import sys
import time
import tomllib

from .app import QabatBot
from .knowledge import system_prompt
from .llm import Ollama
from .store import Store
from .telegram import Telegram, TelegramError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _models():
    path = os.path.join(ROOT, "jarvis", "config", "settings.toml")
    try:
        with open(path, "rb") as f:
            m = tomllib.load(f).get("models", {})
        return m.get("local", ""), m.get("local_fast", "")
    except OSError:
        return "", ""


def main():
    local, fast = _models()
    owner = os.environ.get("QABAT_OWNER_CHAT_ID")
    prices_on = os.environ.get("QABAT_PRICES", "off").lower() == "on"
    db = os.environ.get("QABAT_DB") or os.path.join(ROOT, "data", "qabat-bot.sqlite")
    os.makedirs(os.path.dirname(db), exist_ok=True)
    try:
        tg = Telegram(os.environ.get("QABAT_TG_BOT_TOKEN", ""))
    except TelegramError as e:
        sys.exit(str(e))
    store = Store(db)
    llm = Ollama(os.environ.get("QABAT_OLLAMA_URL", "http://127.0.0.1:11434"),
                 os.environ.get("QABAT_MODEL", local), os.environ.get("QABAT_MODEL_FAST", fast))
    bot = QabatBot(tg, llm, store, int(owner) if owner else None, system_prompt(prices_on=prices_on), prices_on)
    if owner is None:
        print("QABAT_OWNER_CHAT_ID не задан: добавьте бота в группу с темами, напишите там /id и впишите номер.")
    print(f"Бот Qabat запущен. Модель: {llm.model or '—'}, запасная: {llm.fast_model or '—'}. Цены: {'да' if prices_on else 'нет'}.")
    offset = int(store.get("offset", 0)) or None
    while True:
        try:
            for upd in tg.get_updates(offset):
                offset = upd["update_id"] + 1
                try:
                    bot.handle(upd)
                except Exception as e:  # одно сообщение не должно останавливать бота
                    print("Ошибка в сообщении:", e)
                store.set("offset", offset)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Нет связи с Telegram, повтор через 5 с:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
