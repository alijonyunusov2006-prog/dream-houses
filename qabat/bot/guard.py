# Проверка ответа модели перед отправкой клиенту и правила передачи мастеру.
# Модель может ошибиться — правила владельца здесь проверяет код, а не модель.
import re

_MONEY = re.compile(r"(\d[\d\s.,–-]*\s*(сомони|сомонӣ|смн|сом\b|tjs|\$|долл))|(\b(сомони|сомонӣ)\b)", re.I)
_FORBIDDEN = re.compile(r"\b(готово|готов к выдаче|оплата получена|предоплат\w*|скидк\w*)\b", re.I)
_SENT = re.compile(r"(?<=[.!?…])\s+")
PRICE_STUB = "Цену уточнит мастер — напишите размер и цвет."
FALLBACK = "Спасибо! Передал ваш вопрос мастеру, он ответит здесь."

HANDOFF = [
    ("жалоба", re.compile(r"жалоб|сломал|треснул|развалил|не работает|верните|возврат|обман|плохо напечат|брак|шикоят|шикаст", re.I)),
    ("опт", re.compile(r"\b([3-9]\d|\d{3,})\s*(шт|штук|дона|та)\b|\bопт\w*", re.I)),
    ("деталь", re.compile(r"восстанов|деталь|запчаст|қисм", re.I)),
    ("как на картинке", re.compile(r"как на (картинк|фото)|по фото|мисли расм", re.I)),
    ("макет", re.compile(r"макет", re.I)),
]

TJ_LETTERS = re.compile(r"[ӣӯҳқғҷ]", re.I)


def lang_of(text: str) -> str:
    return "tj" if TJ_LETTERS.search(text or "") else "ru"


def handoff_reason(text: str) -> str | None:
    for reason, rx in HANDOFF:
        if rx.search(text or ""):
            return reason
    return None


def clean_reply(reply: str, prices_on: bool = False) -> str:
    """Убирает предложения с ценой (пока цены на паузе) и запрещённые обещания."""
    reply = (reply or "").strip()
    if not reply:
        return FALLBACK
    out, priced = [], False
    for s in _SENT.split(reply):
        if not prices_on and _MONEY.search(s):
            priced = True
            continue
        if _FORBIDDEN.search(s):
            continue
        out.append(s)
    if priced:
        out.append(PRICE_STUB)
    text = " ".join(out).strip()
    return text or FALLBACK
