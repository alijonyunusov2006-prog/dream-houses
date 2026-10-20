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
from datetime import datetime
from pathlib import Path

from .bot import ROOT, ClaudeExecutor, JarvisBot, load_env
from .channels import Broadcast, VoiceOut, WebFeed
from .controller import Controller
from .local import LocalBrain
from .ollama import Ollama
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
        subprocess.Popen([edge, f"--app={url}", "--start-maximized", f"--user-data-dir={ROOT / 'data' / 'edge-main'}"])   # свой профиль: размер окна слушается
    except OSError:
        webbrowser.open(url)


PILL_W, PILL_H = 420, 64


def open_pill(url: str, width: int = PILL_W, height: int = PILL_H) -> None:
    """Живой JARVIS «сверху»: маленькое окно вверху экрана по центру, поверх всех окон."""
    edge = shutil.which("msedge") or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    try:
        import ctypes
        sw = ctypes.windll.user32.GetSystemMetrics(0)
    except Exception:
        sw = 1920
    left = max(0, (sw - width) // 2)
    try:
        subprocess.Popen([edge, f"--app={url}?mode=pill", f"--window-size={width},{height}",
                          f"--window-position={left},8", f"--user-data-dir={ROOT / 'data' / 'edge-pill'}"])   # отдельный профиль: не прилипает к главному окну
    except OSError:
        webbrowser.open(url + "?mode=pill")
        return
    threading.Thread(target=_pin_on_top, args=("JARVIS",), daemon=True).start()


def _pin_on_top(title: str, tries: int = 60, max_height: int = 120) -> None:
    """Через Windows: среди окон с таким заголовком взять МАЛЕНЬКОЕ (таблетку) и закрепить поверх остальных.

    У главного окна и у таблетки заголовок одинаковый («JARVIS»), поэтому ищем по высоте окна.
    """
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def find():
            found = []

            def cb(h, _):
                n = u.GetWindowTextLengthW(h)
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(h, buf, n + 1)
                if buf.value == title and u.IsWindowVisible(h):
                    r = wintypes.RECT()
                    u.GetWindowRect(h, ctypes.byref(r))
                    if 0 < r.bottom - r.top <= max_height:
                        found.append(h)
                return True
            u.EnumWindows(proc(cb), 0)
            return found

        for _ in range(tries):
            for h in find():
                u.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)   # HWND_TOPMOST, NOMOVE|NOSIZE|SHOWWINDOW
                return
            time.sleep(0.25)
        log.warning("окно «сверху» не найдено — закрепить не удалось")
    except Exception:
        log.exception("не удалось закрепить окно сверху")


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


def start_phone(settings: dict, web, tg, tg_owner, token: str):
    """JARVIS в Телеграме как приложение (решение владельца: [phone] enabled). Выключено — кнопка «JARVIS» снята."""
    from urllib.parse import urlparse
    from .phone import set_menu, start_tunnel
    web.tg_token, web.owner_id = token, tg_owner          # проверка подписи Телеграма — только владелец
    if not (tg and tg_owner):
        return None
    ph = settings.get("phone", {})
    if not ph.get("enabled"):
        try:
            set_menu(tg, tg_owner, None)
        except Exception:
            log.warning("кнопку меню бота не сбросил (нет связи?)")
        return None

    def on_url(url: str) -> None:
        web.public_host = urlparse(url).hostname
        set_menu(tg, tg_owner, url)
        log.info("окно JARVIS в Телеграме: кнопка «JARVIS» обновлена")
    try:
        from .webui import REMOTE_PORT
        serve(web, REMOTE_PORT, remote=True)          # отдельная дверь: только подпись владельца, окна ПК закрыты
        return start_tunnel(Path(ph.get("cloudflared", r"C:\Jarvis\tools\cloudflared.exe")), REMOTE_PORT, on_url)
    except Exception:
        log.exception("туннель не запустился — окно в Телеграме недоступно, остальное работает")
        return None


def start_voice(settings: dict):
    """Служба голоса JARVIS (отдельное окружение в C:\\Jarvis\\golos). Нет её — окно читает голосом браузера."""
    sp = settings.get("speech", {})
    py = Path(sp.get("tts_python", r"C:\Jarvis\golos\.venv\Scripts\python.exe"))
    script = Path(sp.get("tts_script", r"C:\Jarvis\golos\jarvis_tts_server.py"))
    if already_running(8766):
        return None
    if not (py.exists() and script.exists()):
        log.warning("служба голоса не найдена (%s) — будет голос браузера", script)
        return None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log_file = open(ROOT / "data" / "logs" / "voice.log", "ab")
    return subprocess.Popen([str(py), str(script)], cwd=str(script.parent), stdout=log_file, stderr=log_file,
                            creationflags=flags)


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
    m = settings.get("models", {})
    bot.local = LocalBrain(Ollama("http://127.0.0.1:11434", m.get("local_fast", "qwen3.5:4b"), timeout=20))   # простые вопросы — бесплатно
    vault = Path(os.environ.get("OBSIDIAN_VAULT", r"C:\Users\alijo\OneDrive\Документы\Obsidian Vault"))
    if vault.exists():
        bot.memory_roots.append(vault)

    stop = threading.Event()
    parallel = max(1, int(settings.get("claude_code", {}).get("max_parallel", 3)))   # до 3 задач сразу
    for i in range(parallel):
        threading.Thread(target=_loop, args=(bot.work_once, stop, 5, f"исполнитель {i + 1}"), daemon=True).start()
    threading.Thread(target=_loop, args=(bot.check_alerts, stop, 30, "контролёр"), daemon=True).start()
    web = JarvisWeb(bot, feed, ROOT / "data" / "tmp")
    if tg and tg_owner and settings.get("telegram", {}).get("voice_replies", True):
        bc.voice = VoiceOut(tg, tg_owner, speech=web.speech)   # ответы в Telegram ещё и голосом JARVIS
    web.on_pill = lambda: open_pill(f"http://127.0.0.1:{PORT}/")
    web.projects_dir = vault / "Проекты" if vault.exists() else None   # 3D-офис: что идёт по проектам
    bot.telegram_on = tg is not None
    web.on_office = bot.on_office = lambda: open_window(f"http://127.0.0.1:{PORT}/office")
    serve(web, PORT)
    try:
        voice = start_voice(settings)
    except Exception:
        log.exception("служба голоса не запустилась — будет голос браузера")
        voice = None
    if tg:
        threading.Thread(target=telegram_loop, args=(tg, bot, feed, bc, stop), daemon=True).start()
    tunnel = start_phone(settings, web, tg, tg_owner, token)

    url = f"http://127.0.0.1:{PORT}/"
    hello = ROOT / "data" / "hello.txt"                     # «на связи» — раз в день, а не при каждом перезапуске
    today = datetime.now().date().isoformat()
    if not hello.exists() or hello.read_text(encoding="utf-8").strip() != today:
        bc.send(owner, "JARVIS на связи, сэр. Скажите «Джарвис» — и задание." +
                ("" if tg_owner else " Телеграм пока не подключён."))
        hello.parent.mkdir(parents=True, exist_ok=True)
        hello.write_text(today, encoding="utf-8")
    print(f"JARVIS запущен: {url}  — это окно не закрывайте.", flush=True)
    if os.environ.get("JARVIS_NO_WINDOW") != "1":
        open_window(url)
        if settings.get("window", {}).get("pill_on_start", True):
            threading.Timer(3.0, open_pill, args=(url,)).start()      # живой JARVIS сверху — тоже сразу
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()
    finally:
        if voice:
            voice.terminate()
        if tunnel:
            tunnel.terminate()


if __name__ == "__main__":
    main()
