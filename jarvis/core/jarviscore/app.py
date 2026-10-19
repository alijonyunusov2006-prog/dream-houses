"""Запуск JARVIS: окно на ПК (всегда) + Telegram (если вписан ключ).

``python -m jarviscore.app`` из папки ``jarvis`` (или ``Запустить-JARVIS.cmd``).
Один процесс, одна очередь задач: что сказано в окне — видно в Telegram, и наоборот.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
import tomllib
import webbrowser
from pathlib import Path

from .bot import ROOT, ClaudeExecutor, JarvisBot, load_env
from .channels import Broadcast, WebFeed
from .controller import Controller
from .webui import JarvisWeb, serve

log = logging.getLogger("jarvis.app")
PORT = 8765
WEB_OWNER = 0          # «номер чата» окна, когда Telegram ещё не настроен


def _loop(step, stop: threading.Event, every: float, name: str) -> None:
    while not stop.is_set():
        try:
            step()
        except Exception:
            log.exception(name)
        stop.wait(every)


def open_window(url: str) -> None:
    """Отдельное окно без адресной строки (Edge есть в любой Windows), иначе — обычный браузер."""
    edge = shutil.which("msedge") or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    try:
        subprocess.Popen([edge, f"--app={url}", "--window-size=1280,820"])
    except OSError:
        webbrowser.open(url)


def telegram_loop(tg, bot: JarvisBot, feed: WebFeed, bc: Broadcast, stop: threading.Event) -> None:
    offset_file = ROOT / "data" / "tg_offset.txt"
    offset = int(offset_file.read_text()) if offset_file.exists() else None
    while not stop.is_set():
        try:
            for u in tg.get_updates(offset):
                offset = u["update_id"] + 1
                offset_file.write_text(str(offset))
                _from_telegram(u, tg, bot, feed, bc)
        except Exception:
            log.exception("связь с Telegram")
            time.sleep(10)


def _from_telegram(u: dict, tg, bot: JarvisBot, feed: WebFeed, bc: Broadcast) -> None:
    msg = u.get("message") or {}
    chat = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if bc.tg_chat is None:                       # владелец ещё не вписан — работает только /id
        if text.startswith("/id"):
            tg.send(chat, f"Номер этого чата: {chat}. Впишите его в jarvis/.env как OWNER_CHAT_ID.")
        return
    if chat != bc.tg_chat:
        return                                    # чужие — молча мимо
    # сообщение владельца появляется и в окне; номера переводим в номера окна
    shown = text or ("🎙 голосовое" if (msg.get("voice") or msg.get("audio")) else "")
    if not shown:
        return
    reply_tg = (msg.get("reply_to_message") or {}).get("message_id")
    reply_web = bc.web_of(reply_tg)
    web_id = feed.add_owner(shown, reply_web)
    bc.link(web_id, msg["message_id"])
    msg = dict(msg, message_id=web_id, chat={"id": bot.owner, "type": "private"},
               **({"reply_to_message": {"message_id": reply_web}} if reply_web else {}))
    if not reply_web:
        msg.pop("reply_to_message", None)
    try:
        bot.handle({"update_id": u["update_id"], "message": msg})
    except Exception:
        log.exception("сообщение %s", u.get("update_id"))


def already_running(port: int = PORT) -> bool:
    import socket

    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    from .stt import Transcriber
    from .telegram import Telegram

    if already_running():          # второй щелчок по ярлыку — просто показать окно работающего JARVIS
        print("JARVIS уже запущен — открываю окно.", flush=True)
        open_window(f"http://127.0.0.1:{PORT}/")
        return

    (ROOT / "data" / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=ROOT / "data" / "logs" / "bot.log", level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_env(ROOT / ".env")
    settings = tomllib.loads((ROOT / "config" / "settings.toml").read_text(encoding="utf-8"))
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_owner = int(os.environ["OWNER_CHAT_ID"]) if os.environ.get("OWNER_CHAT_ID", "").strip() else None
    tg = Telegram(token) if token else None

    feed = WebFeed(ROOT / "data" / "feed.jsonl")
    bc = Broadcast(feed, tg, tg_owner)
    ctl = Controller.load(ROOT / "data" / "tasks.json",
                          escalation_min=settings.get("telegram", {}).get("escalation_minutes", 10))
    sp = settings.get("speech", {})
    owner = tg_owner if tg_owner is not None else WEB_OWNER
    bot = JarvisBot(bc, ctl, ClaudeExecutor(settings),
                    Transcriber(sp.get("stt_model", "large-v3"), sp.get("stt_language", "ru")), owner_chat=owner)
    bot.report_hour = settings.get("telegram", {}).get("report_hour", 8)
    vault = Path(os.environ.get("OBSIDIAN_VAULT", r"C:\Users\alijo\OneDrive\Документы\Obsidian Vault"))
    if vault.exists():
        bot.memory_roots.append(vault)

    stop = threading.Event()
    parallel = max(1, int(settings.get("claude_code", {}).get("max_parallel", 3)))   # до 3 задач сразу
    for i in range(parallel):
        threading.Thread(target=_loop, args=(bot.work_once, stop, 5, f"исполнитель {i + 1}"), daemon=True).start()
    threading.Thread(target=_loop, args=(bot.check_alerts, stop, 30, "контролёр"), daemon=True).start()
    serve(JarvisWeb(bot, feed, ROOT / "data" / "tmp"), PORT)
    if tg:
        threading.Thread(target=telegram_loop, args=(tg, bot, feed, bc, stop), daemon=True).start()

    url = f"http://127.0.0.1:{PORT}/"
    bc.send(owner, "JARVIS на связи. Пишите или говорите задание." +
            ("" if tg_owner else "\n(Telegram пока не подключён — см. docs/БОТ-JARVIS.md)"))
    print(f"JARVIS запущен: {url}  — это окно не закрывайте.", flush=True)
    if os.environ.get("JARVIS_NO_WINDOW") != "1":
        open_window(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
