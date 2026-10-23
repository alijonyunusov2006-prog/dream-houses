"""Единый фильтр секретов: строка, похожая на пароль, ключ, токен, логин или номер карты, — выбрасывается целиком.

Используют память («вспомни…») и 3D-офис (/api/office). Ревью 2026-10-21: фильтр офиса был уже, чем у памяти.
Слово «секретарь» — не секрет.
"""

from __future__ import annotations

import re

SECRET = re.compile(
    r"парол|password|passwd|\bpwd\b|\bpass\b|credential|логин|\blogin\b|bearer|"
    r"токен|token|secret|секрет(?!ар)|api[_ ]?key|ключ\s*(?:api|бота|доступа)|"
    r"\bпин(?:-?код)?\b|\bpin\b|"
    r"=\s*\S{20,}|\bsk-[A-Za-z0-9_-]{10,}|\bghp_[A-Za-z0-9]{10,}|\b\d{8,10}:AA[\w-]{20,}|"
    r"\b(?:\d[ -]?){13,19}\b",                     # номер карты
    re.I)


def has_secret(line: str) -> bool:
    return bool(SECRET.search(line or ""))


def drop_secret_lines(text: str) -> str:
    return "\n".join(line for line in (text or "").splitlines() if not has_secret(line))
