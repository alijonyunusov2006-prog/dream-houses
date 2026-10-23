"""JARVIS в Телеграме как приложение: туннель Cloudflare + кнопка «JARVIS» в боте.

Телеграм открывает мини-приложение только по адресу https в интернете, а JARVIS живёт на ПК (127.0.0.1).
Бесплатный «быстрый туннель» cloudflared даёт временный адрес ``https://<слова>.trycloudflare.com``,
который ведёт на окно JARVIS. Адрес меняется при каждом запуске — поэтому при каждом запуске
обновляем кнопку меню бота. Внутрь пускает только подпись Телеграма владельца (``tgauth``, ``webui``).
Включается настройкой ``[phone] enabled = true`` (решение владельца), выключено по умолчанию.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
from pathlib import Path

log = logging.getLogger("jarvis.phone")
URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def find_url(line: str) -> str | None:
    m = URL.search(line or "")
    return m.group(0) if m else None


def set_menu(tg, owner: int, url: str | None) -> None:
    """Кнопка меню в чате с ботом: «JARVIS» открывает окно; без адреса — обычное меню команд."""
    button = {"type": "web_app", "text": "JARVIS", "web_app": {"url": url}} if url else {"type": "default"}
    tg.call("setChatMenuButton", chat_id=owner, menu_button=button)


def start_tunnel(exe: Path, port: int, on_url) -> subprocess.Popen | None:
    """Запустить cloudflared и вызвать on_url(адрес), когда туннель поднимется."""
    if not exe.exists():
        log.warning("нет %s — JARVIS в Телеграме как приложение выключен", exe)
        return None
    proc = subprocess.Popen([str(exe), "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def watch():
        sent = False
        for line in proc.stderr:                     # cloudflared пишет адрес в журнал
            url = find_url(line)
            if url and not sent:
                sent = True
                try:
                    on_url(url)
                except Exception:
                    log.exception("кнопка «JARVIS» в боте не обновилась")
        log.warning("туннель остановился (код %s)", proc.poll())

    threading.Thread(target=watch, daemon=True, name="jarvis-tunnel").start()
    return proc
