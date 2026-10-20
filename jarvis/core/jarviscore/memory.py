"""Память JARVIS: «вспомни, что мы решили про …» — поиск по заметкам (brain/ и хранилище Obsidian).

Без облака и без нейросети: строки .md, где встречается больше всего слов вопроса (по основам слов —
«цены»/«цену», «Джарвис»/«Джарвиса» совпадают). Мгновенно и бесплатно. Позже можно заменить на
поиск по смыслу (mem0), интерфейс тот же: search(запрос, папки) → находки.

Бережно: не больше 4000 файлов и 5 секунд, файлы до 1 МБ, служебные папки пропускаем, файлы OneDrive
«только в облаке» не трогаем (иначе начнут скачиваться). Строки с паролями и ключами в ответ не попадают.
"""

from __future__ import annotations

import os
import re
import stat
import time
from dataclasses import dataclass
from pathlib import Path

RECALL = re.compile(r"^\s*(?:вспомни\w*|напомни\w*|что\s+мы\s+(?:решили|говорили|обсуждали)|"
                    r"найди\s+в\s+памяти|что\s+я\s+(?:говорил|просил|решил)|где\s+лежит|где\s+лежат)", re.I)
STOP = {"что", "мы", "про", "о", "об", "в", "во", "на", "и", "а", "с", "по", "у", "к", "это", "этот", "эта", "как",
        "какой", "какая", "какие", "решили", "говорили", "обсуждали", "вспомни", "напомни", "найди", "памяти",
        "где", "лежит", "лежат", "мне", "я", "ты", "он", "за", "для", "же", "ли", "не", "то"}
WORD = re.compile(r"[a-zа-яё0-9]+", re.I)
SECRET = re.compile(r"парол|password|passwd|токен|token|secret|секрет|api[_ ]?key|ключ\s*(?:api|бота|доступа)|=\s*\S{20,}", re.I)
SKIP_DIRS = {".obsidian", ".git", ".trash", "node_modules", "graphify-out", ".venv", "__pycache__"}
MAX_BYTES = 1_000_000
CLOUD_ONLY = 0x400000 | 0x1000        # RECALL_ON_DATA_ACCESS | OFFLINE (OneDrive «только в облаке»)


@dataclass(frozen=True)
class Hit:
    file: Path
    lineno: int
    line: str
    score: float


def is_recall(text: str) -> bool:
    return bool(RECALL.match(text or ""))


def _stem(w: str) -> str:
    w = w.lower().replace("ё", "е")
    return w[:max(4, len(w) - 2)] if len(w) > 4 else w


def _terms(text: str) -> set[str]:
    return {_stem(w) for w in WORD.findall(text or "") if w.lower() not in STOP and len(w) > 1}


def _md_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if name.endswith(".md"):
                yield Path(dirpath) / name


def _readable(f: Path) -> bool:
    try:
        st = f.stat()
    except OSError:
        return False
    return st.st_size <= MAX_BYTES and not (getattr(st, "st_file_attributes", 0) & CLOUD_ONLY)


def search(query: str, roots: list[Path], limit: int = 5, max_files: int = 4000, max_sec: float = 5.0) -> list[Hit]:
    terms = _terms(query)
    if not terms:
        return []
    hits: list[Hit] = []
    seen, deadline = 0, time.monotonic() + max_sec
    for root in map(Path, roots):
        if not root.exists():
            continue
        for f in _md_files(root):
            seen += 1
            if seen > max_files or time.monotonic() > deadline:
                break
            if not _readable(f):
                continue
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                found = terms & _terms(line)
                if found and not SECRET.search(line):
                    score = len(found) / len(terms) + (0.2 if f.stem.lower() in ("decided", "always", "always-ask") else 0)
                    hits.append(Hit(f, i, line.strip()[:300], score))
    hits.sort(key=lambda h: (-h.score, len(h.line)))
    best = [h for h in hits if h.score >= max(0.34, hits[0].score * 0.6)] if hits else []
    return best[:limit]


def answer(query: str, roots: list[Path]) -> str:
    hits = search(query, roots)
    if not hits:
        return "В моих записях ничего не нашёл, сэр. Скажите иначе или дайте задание — поищу глубже."
    out = ["Вот что нашёл в записях, сэр:"]
    for h in hits[:3]:
        out.append("• " + _plain(h.line))
    return "\n".join(out)


def _plain(line: str, limit: int = 220) -> str:
    """Строка заметки без разметки: таблицы, звёздочки, ссылки [[…]], пути в `…` — читать и слушать по-человечески."""
    t = re.sub(r"\[\[([^\]|]+)\|?([^\]]*)\]\]", lambda m: m.group(2) or m.group(1), line)
    t = re.sub(r"`[^`]*`", "", t)
    t = re.sub(r"^\s*\|?\s*\d{4}-\d{2}-\d{2}\s*\|", "", t)          # дата в первой колонке таблицы решений
    t = re.sub(r"\|\s*[\w-]+\s*\|\s*$", "", t)                      # ярлык в последней колонке
    t = t.replace("|", " — ")
    t = re.sub(r"[*_#>]+", "", t)
    t = re.sub(r"\s*—\s*(—\s*)+", " — ", t)
    t = re.sub(r"\s+", " ", t).strip(" —-")
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"
