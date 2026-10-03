"""Правило удаления владельца («три раза»).

Владелец сказал (2026-10-03): ничего важного не удалять; обычное удалять только после двух «да»;
важное — не удалять, а дать ссылку или путь, чтобы он удалил сам. Если он настаивает в третий раз
или говорит «понимаю, что это важно, но разрешаю удалить» (со второго раза) — удалить, сначала
сделав резервную копию.

Как это работает:

* ``classify(target)`` — ``ordinary`` или ``important`` по шаблонам из ``config/allowlist.toml``
  ``[deletion]``. Всё вне разрешённых папок тоже считается важным.
* ``request(target, ...)`` — владелец просит удалить. Для обычного — просим первое «да».
  Для важного — 1-й и 2-й раз отказываем со ссылкой «удалите сами», 3-й раз (или осознанная фраза
  со второго раза) — разрешаем.
* ``confirm(target)`` — «да» владельца на обычное удаление. Второе «да» разрешает.
* Разрешение выдаётся на **одну конкретную команду** на 15 минут. Хук Claude Code пропускает
  ровно эту команду (``consume_unlock``) и только один раз.

Состояние хранится в ``data/deletion.json`` (не в Git).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


class Level(str, Enum):
    ORDINARY = "ordinary"
    IMPORTANT = "important"


class Action(str, Enum):
    ASK_CONFIRM = "ask_confirm"        # обычное: нужно «да» (первое или второе)
    SELF_SERVICE = "self_service"      # важное: не удаляем, даём ссылку — удалите сами
    UNLOCKED = "unlocked"              # можно удалять (одна команда, 15 минут)


# «Понимаю, что это важно, но разрешаю удалить» и близкие формулировки.
INFORMED_CONSENT = re.compile(
    r"(понима\w*|осозна\w*|знаю)[^.?!]{0,60}важн\w*[^.?!]{0,60}(разреша\w*|удаля\w*|удали\w*|можно)",
    re.IGNORECASE,
)


def _norm(target: str) -> str:
    t = os.path.expandvars(os.path.expanduser(target.strip().strip('"')))
    return t.replace("\\", "/").rstrip("/").lower()


def _is_path(t: str) -> bool:
    return t.startswith("/") or bool(re.match(r"^[a-z]:/", t))


def _match(t: str, pattern: str) -> bool:
    p = _norm(pattern)
    return t == p or fnmatch.fnmatch(t, p) or fnmatch.fnmatch(t, p.rstrip("*").rstrip("/"))


@dataclass
class Outcome:
    action: Action
    level: Level
    count: int
    message: str
    backup_required: bool = False


@dataclass
class _Entry:
    target: str
    level: str
    demands: int = 0
    confirms: int = 0
    first_at: float = 0.0
    last_at: float = 0.0


@dataclass
class _Unlock:
    command: str
    target: str
    expires_at: float
    backup_required: bool


@dataclass
class DeletionGuard:
    state_path: Path
    important_globs: list[str] = field(default_factory=list)
    ordinary_globs: list[str] = field(default_factory=list)
    allowed_dirs: list[str] = field(default_factory=list)
    root: Path | None = None
    window_hours: float = 24.0
    unlock_minutes: float = 15.0
    now: Callable[[], float] = time.time

    # ------------------------------------------------------------ загрузка
    @classmethod
    def from_allowlist(cls, allowlist_path: Path | str, state_path: Path | str, **kw) -> "DeletionGuard":
        import tomllib

        data = tomllib.loads(Path(allowlist_path).read_text(encoding="utf-8"))
        dele = data.get("deletion", {})
        return cls(
            state_path=Path(state_path),
            important_globs=list(dele.get("important", [])),
            ordinary_globs=list(dele.get("ordinary", [])),
            allowed_dirs=list(data.get("paths", {}).get("allowed", [])),
            window_hours=float(dele.get("window_hours", 24)),
            unlock_minutes=float(dele.get("unlock_minutes", 15)),
            **kw,
        )

    def _load(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"entries": {}, "unlocks": []}

    def _save(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # --------------------------------------------------------- классификация
    def classify(self, target: str) -> Level:
        """Важное или обычное. Сомнение всегда в пользу «важного»."""
        t = _norm(target)
        if self.root is not None and not _is_path(t) and ("/" in t or "." in t) and ":" not in t:
            t = _norm(str(Path(self.root) / target))           # относительный путь — от корня jarvis
        if any(_match(t, pat) for pat in self.ordinary_globs):
            return Level.ORDINARY                               # временное и кэш — обычное даже внутри важного
        if any(_match(t, pat) for pat in self.important_globs):
            return Level.IMPORTANT
        if not _is_path(t):
            return Level.IMPORTANT                              # облако, CRM, репозитории, аккаунты — по умолчанию важное
        if self.allowed_dirs and not any(t == _norm(d) or t.startswith(_norm(d) + "/") for d in self.allowed_dirs):
            return Level.IMPORTANT                              # вне разрешённых папок — всегда важное
        return Level.ORDINARY

    def _entry(self, state: dict, target: str) -> _Entry:
        key = _norm(target)
        raw = state["entries"].get(key)
        now = self.now()
        if raw is None or now - raw["last_at"] > self.window_hours * 3600:
            e = _Entry(target=target, level=self.classify(target).value, first_at=now, last_at=now)
        else:
            e = _Entry(**raw)
        return e

    def _put(self, state: dict, e: _Entry) -> None:
        e.last_at = self.now()
        state["entries"][_norm(e.target)] = asdict(e)

    def _unlock(self, state: dict, e: _Entry, command: str | None, backup: bool) -> None:
        state["unlocks"].append(asdict(_Unlock(
            command=(command or "").strip(), target=e.target,
            expires_at=self.now() + self.unlock_minutes * 60, backup_required=backup)))
        state["entries"].pop(_norm(e.target), None)    # счётчик начинается заново

    # --------------------------------------------------------------- запрос
    def request(self, target: str, owner_text: str = "", command: str | None = None,
                where: str | None = None) -> Outcome:
        """Владелец просит удалить ``target``. ``where`` — ссылка или путь для «удалите сами»."""
        state = self._load()
        e = self._entry(state, target)
        e.demands += 1
        level = Level(e.level)

        if level is Level.ORDINARY:
            self._put(state, e)
            self._save(state)
            return Outcome(Action.ASK_CONFIRM, level, e.demands,
                           f"Удалить «{target}»? Ответьте «да». После этого спрошу ещё раз — удаляю только после двух «да».")

        informed = bool(INFORMED_CONSENT.search(owner_text or ""))
        if e.demands >= 3 or (e.demands >= 2 and informed):
            self._unlock(state, e, command, backup=True)
            self._save(state)
            why = "вы попросили в третий раз" if e.demands >= 3 else "вы подтвердили, что понимаете важность"
            return Outcome(Action.UNLOCKED, level, e.demands,
                           f"Удаляю «{target}»: {why}. Сначала делаю резервную копию, потом удаляю и пришлю отчёт.",
                           backup_required=True)

        self._put(state, e)
        self._save(state)
        place = f" Вот где это: {where}" if where else ""
        left = 3 - e.demands
        return Outcome(Action.SELF_SERVICE, level, e.demands,
                       f"«{target}» — важное, сам не удаляю.{place} Зайдите и удалите сами. "
                       f"Если всё же нужно, чтобы удалил я, — попросите ещё {left} раз(а) "
                       f"или скажите: «понимаю, что это важно, но разрешаю удалить».")

    def confirm(self, target: str, command: str | None = None) -> Outcome:
        """«Да» владельца на удаление обычного ``target``."""
        state = self._load()
        e = self._entry(state, target)
        level = Level(e.level)
        if level is Level.IMPORTANT:
            return self.request(target, command=command)   # для важного «да» = ещё одна просьба
        if e.demands == 0:
            e.demands = 1                                   # «да» без вопроса считаем просьбой
        e.confirms += 1
        if e.confirms >= 2:
            self._unlock(state, e, command, backup=False)
            self._save(state)
            return Outcome(Action.UNLOCKED, level, e.demands, f"Удаляю «{target}» (два «да» получено). Сначала — в корзину, если это возможно.")
        self._put(state, e)
        self._save(state)
        return Outcome(Action.ASK_CONFIRM, level, e.demands, f"Точно удалить «{target}»? Ответьте «да» ещё раз.")

    # ------------------------------------------------------------- для хука
    def consume_unlock(self, command: str) -> _Unlock | None:
        """Если ``command`` разрешена владельцем — вернуть разрешение и погасить его (один раз)."""
        state = self._load()
        now = self.now()
        cmd = command.strip()
        found = None
        keep = []
        for raw in state.get("unlocks", []):
            u = _Unlock(**raw)
            if u.expires_at < now:
                continue
            if found is None and u.command and u.command == cmd:
                found = u
                continue
            keep.append(raw)
        if found is not None or len(keep) != len(state.get("unlocks", [])):
            state["unlocks"] = keep
            self._save(state)
        return found
