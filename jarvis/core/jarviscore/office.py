"""Живые данные для 3D-офиса: кто из агентов работает, кто ждёт владельца, кто свободен; что идёт по проектам.

Источник правды — очередь задач JARVIS (агент задачи выбирается при разборе, ``checkpoint["agent"]``),
список агентов — ``.claude/agents/*.md``, проекты — страницы второго мозга ``Obsidian Vault/Проекты/*.md``.
Ничего не выдумывает: нет данных — пусто, а не демо.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .planner import State

JARVIS_ID = "jarvis"
# строка с этим — выбрасывается целиком (пароли, ключи, токены); слово «секретарь» не трогаем
from .secrets_filter import SECRET   # единый фильтр: пароли, ключи, токены, логины, номера карт
# русские имена там, где в описании агента латиница (владелец не читает по-английски)
RU_ROLE = {"3d": "3D-печать и модели", "archicad": "Планировки в Архикаде", "academy": "Академия Dream House",
           "crm": "Учёт клиентов и задач", "browser": "Работа с сайтами", "content": "Контент",
           "archviz": "3D-визуализатор", "coach": "Наставник", "strategist": "Стратег",
           "quality": "Качество и клиенты", "sysadmin": "Сисадмин компьютера"}
_ROLE = re.compile(r"^description:\s*([^.\n]+)", re.M)
_NAME = re.compile(r"^name:\s*(\S+)", re.M)
_WORKED = re.compile(r"\*\*Работали:\*\*\s*([\d-]+)(?:\s*—\s*([\d-]+))?(?:\s*\((\d+)\s*дн)?")
_WHERE = re.compile(r"\*\*Где на диске:\*\*\s*(.+)")
_SUMMARY = re.compile(r"^>\s*(.+)$", re.M)
_DONE_WORDS = re.compile(r"работа закончена|дело закончено|всё готово|всё сделано|сдан[оа]?\b|завершен[оа]?", re.I)
QUIET_DAYS = 14          # дольше не трогали — «стоит»


def _clean(text: str, limit: int) -> str:
    t = "\n".join(line for line in (text or "").splitlines() if not SECRET.search(line))   # строка с секретом — целиком вон
    t = re.sub(r"\[\[([^\]|]+)\|?([^\]]*)\]\]", lambda m: m.group(2) or m.group(1), t)   # [[ссылка]] → текст
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[почта]", t)          # чужие адреса почты на экране не показываем
    t = re.sub(r"\+?\d[\d\s()-]{8,}\d", "[телефон]", t)              # и телефоны
    t = re.sub(r"[*_`#>]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def load_agents(agents_dir: Path) -> list[dict]:
    """[{id, role}] из .claude/agents/*.md; первым — сам JARVIS."""
    out = [{"id": JARVIS_ID, "role": "Главный управляющий"}]
    for f in sorted(agents_dir.glob("*.md")):
        head = f.read_text(encoding="utf-8", errors="replace")[:1500]
        name = (_NAME.search(head) or [None, f.stem])[1]
        role = _ROLE.search(head)
        out.append({"id": name, "role": RU_ROLE.get(name) or (_clean(role.group(1), 60) if role else name)})
    return out


def role_of(agents_dir: Path, agent: str) -> str:
    """Русское название агента («3D-визуализатор») — владелец не читает по-английски."""
    return next((a["role"] for a in load_agents(agents_dir) if a["id"] == agent), "JARVIS")


def agent_ids(agents_dir: Path) -> list[str]:
    return [a["id"] for a in load_agents(agents_dir) if a["id"] != JARVIS_ID]


def _agent_of(t, known: set[str]) -> str:
    a = (t.checkpoint or {}).get("agent") or JARVIS_ID
    return a if a in known else JARVIS_ID


def agents_view(agents: list[dict], tasks: list, today) -> list[dict]:
    """Статус каждого агента по задачам: work — делает, wait — ждёт ответа владельца, idle — свободен."""
    known = {a["id"] for a in agents}
    rows = {a["id"]: {**a, "status": "idle", "task": None, "queue": [], "last": None, "done_today": 0} for a in agents}
    for t in sorted(tasks, key=lambda x: x.updated_at):
        row = rows[_agent_of(t, known)]
        brief = {"id": t.id, "title": _clean(t.title, 120)}
        if t.state is State.RUNNING:
            row["status"] = "work"
            row["task"] = {**brief, "state_ru": "в работе"}
        elif t.state is State.WAITING_HUMAN:
            if row["status"] != "work":
                row["status"] = "wait"
                row["task"] = {**brief, "state_ru": "ждёт вашего ответа"}
            else:
                row["queue"].append(brief)
        elif t.state in (State.PENDING, State.PAUSED, State.BLOCKED):
            row["queue"].append(brief)
        elif t.state is State.DONE:
            row["last"] = {**brief, "at": t.updated_at.isoformat(), "text": _clean(t.progress, 220)}
            if t.updated_at.astimezone().date() == today:
                row["done_today"] += 1
    # JARVIS разбирает новые задачи сам — пока очередь не пуста, он занят
    j = rows[JARVIS_ID]
    if j["status"] == "idle" and j["queue"]:
        j["status"] = "work"
        j["task"] = {**j["queue"].pop(0), "state_ru": "разбираю задание"}
    return list(rows.values())


def _section(text: str, title: str) -> str:
    m = re.search(rf"^##\s*{re.escape(title)}\s*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


_PROJ_CACHE: dict = {}
PROJ_TTL = 30            # офис опрашивает каждые 4 с, а файлы второго мозга (OneDrive) читаем не чаще раза в 30 с


def load_projects_cached(projects_dir: Path | None) -> list[dict]:
    key = str(projects_dir)
    at, val = _PROJ_CACHE.get(key, (0.0, None))
    if val is None or time.monotonic() - at > PROJ_TTL:
        val = load_projects(projects_dir)
        _PROJ_CACHE[key] = (time.monotonic(), val)
    return val


def load_projects(projects_dir: Path | None, now: datetime | None = None) -> list[dict]:
    """Проекты из второго мозга: имя, суть, последние даты, «на чём остановились», состояние."""
    if not projects_dir or not projects_dir.is_dir():
        return []
    now = now or datetime.now()
    out = []
    for f in projects_dir.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:                                  # облачный файл OneDrive не скачан — пропускаем
            continue
        m = _WORKED.search(text)
        last = (m.group(2) or m.group(1)) if m else ""
        days = int(m.group(3)) if m and m.group(3) else 0
        nxt = _section(text, "На чём остановились")
        nxt = re.sub(r"_\(итог от [^)]*\)_", "", nxt)
        nxt = "\n".join(line for line in nxt.splitlines() if not SECRET.search(line))   # секреты — до проверки языка
        letters = re.findall(r"[A-Za-zА-Яа-яЁё]", nxt)
        if letters and sum(c.isascii() for c in letters) / len(letters) > 0.5:
            nxt = ""                                     # запись на английском — владелец её не прочтёт
        state = "done" if _DONE_WORDS.search(nxt) else "active"
        try:
            if state == "active" and last and (now - datetime.fromisoformat(last)).days > QUIET_DAYS:
                state = "quiet"
        except ValueError:
            pass
        where = _WHERE.search(text)
        summ = _SUMMARY.search(text)
        out.append({"id": f.stem, "name": f.stem, "summary": _clean(summ.group(1), 160) if summ else "",
                    "last": last, "days": days, "state": state, "next": _clean(nxt, 320),
                    "where": _clean(where.group(1), 160) if where else ""})
    out.sort(key=lambda p: p["last"], reverse=True)
    return out


class Machine:
    """Здоровье ПК: голос, локальная модель, диск, видеокарта. Опрашивается не чаще раза в 20 с."""
    TTL = 20

    def __init__(self, tts_url: str, ollama_url: str = "http://127.0.0.1:11434", disk: str = "C:\\"):
        self.tts_url, self.ollama_url, self.disk = tts_url, ollama_url, disk
        self._at, self._val = 0.0, {}

    @staticmethod
    def _ok(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                return r.status == 200
        except Exception:
            return False

    @staticmethod
    def _gpu() -> int | None:
        exe = shutil.which("nvidia-smi")
        if not exe:
            return None
        try:
            out = subprocess.run([exe, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=3,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            return int(out.strip().splitlines()[0])
        except Exception:
            return None

    def get(self) -> dict:
        if time.monotonic() - self._at < self.TTL and self._val:
            return self._val
        try:
            free = round(shutil.disk_usage(self.disk).free / 1e9)
        except OSError:
            free = None
        self._val = {"voice": self._ok(self.tts_url + "/health"), "local_model": self._ok(self.ollama_url + "/api/tags"),
                     "disk_free_gb": free, "gpu_pct": self._gpu()}
        self._at = time.monotonic()
        return self._val


def snapshot(bot, agents_dir: Path, projects_dir: Path | None, machine: Machine | None) -> dict:
    """Всё для офиса одним ответом /api/office."""
    today = datetime.now().astimezone().date()
    agents = load_agents(agents_dir)
    with bot.lock:
        tasks = list(bot.ctl.sched.tasks.values())
        open_ = [t for t in tasks if t.state in (State.PENDING, State.PAUSED, State.BLOCKED, State.RUNNING,
                                                 State.WAITING_HUMAN)]
        jarvis = {"open": len(open_),
                  "running": sum(t.state is State.RUNNING for t in open_),
                  "waiting": sum(t.state is State.WAITING_HUMAN for t in open_),
                  "done_today": sum(1 for t in tasks if t.state is State.DONE
                                    and t.updated_at.astimezone().date() == today),
                  "telegram": bool(getattr(bot, "telegram_on", False))}
        view = agents_view(agents, tasks, today)
    mach = machine.get() if machine else {}
    return {"updated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "jarvis": jarvis, "agents": view, "projects": load_projects_cached(projects_dir), "machine": mach}


def to_json(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")
