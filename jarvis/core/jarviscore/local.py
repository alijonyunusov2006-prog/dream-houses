"""Простые вопросы — на локальной модели (Ollama на видеокарте), без траты подписки Claude.

«Сколько будет…», «который час», «что такое…», «переведи…» — это не задачи для исполнителя: отвечает
лёгкая модель ``local_fast`` за секунду, бесплатно. Если Ollama не запущена — возвращаем None,
и вопрос идёт обычным путём через Claude.
"""

from __future__ import annotations

import re
from datetime import datetime

SIMPLE = re.compile(
    r"^\s*(?:сколько\s+будет|который\s+час|сколько\s+времени|что\s+такое|кто\s+такой|кто\s+такая|"
    r"переведи|как\s+(?:сказать|будет)\s+по|какой\s+сегодня\s+день|какое\s+сегодня\s+число|"
    r"объясни\s+(?:коротко|простыми)|чем\s+отличается)", re.I)

SYSTEM = ("Ты JARVIS — личный помощник Алиджона (студия Dream House, Душанбе). Отвечай по-русски, коротко "
          "(1–3 предложения), вежливо, обращение «сэр». Сегодня {date}, время {time}. "
          "Не выдумывай факты: если не уверен — скажи, что уточнишь.")


def is_simple(text: str) -> bool:
    return bool(SIMPLE.match(text or ""))


class LocalBrain:
    def __init__(self, llm):
        self.llm = llm          # объект с .reply(system, history) → str | None (как qabat.bot.llm.Ollama)

    def answer(self, text: str) -> str | None:
        now = datetime.now()
        system = SYSTEM.format(date=now.strftime("%d.%m.%Y, %A"), time=now.strftime("%H:%M"))
        try:
            reply = self.llm.reply(system, [{"role": "user", "content": text}])
        except Exception:
            return None
        return (reply or "").strip() or None
