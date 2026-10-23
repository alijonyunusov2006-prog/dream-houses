"""Вход в окно JARVIS из Телеграма (мини-приложение): пускаем только владельца.

Телеграм подписывает данные запуска (initData) ключом бота — подделать подпись без ключа нельзя.
Проверяем по правилам Телеграма: HMAC-SHA256, ключ = HMAC("WebAppData", ключ_бота); плюс номер
пользователя = владелец и подпись не старше 2 часов.
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE = 2 * 3600          # подпись живёт 2 часа (ревью безопасности: меньше вред, если утечёт); дольше — переоткрыть окно


def check(init_data: str, bot_token: str, owner_id: int | None, now: float | None = None,
          max_age: int = MAX_AGE) -> bool:
    if not (init_data and bot_token and owner_id):
        return False
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return False
    got = pairs.pop("hash", "")
    if not got:
        return False
    data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, got):
        return False
    try:
        age = (now or time.time()) - int(pairs.get("auth_date", "0"))
        user = json.loads(pairs.get("user", "{}"))
    except (ValueError, json.JSONDecodeError):
        return False
    if age < -300 or age > max_age:          # из будущего (часы сбиты сильнее 5 мин) или старше срока
        return False
    return user.get("id") == int(owner_id)


def sign(fields: dict, bot_token: str) -> str:
    """Подписать данные так же, как Телеграм (для проверок)."""
    from urllib.parse import urlencode
    data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})
