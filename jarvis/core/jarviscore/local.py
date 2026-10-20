"""Простые вопросы — на локальной модели (Ollama на видеокарте), без траты подписки Claude.

«Сколько будет…», «который час», «что такое…», «переведи…» — это не задачи для исполнителя: отвечает
лёгкая модель ``local_fast`` за секунду, бесплатно. Если Ollama не запущена — возвращаем None,
и вопрос идёт обычным путём через Claude.
"""

from __future__ import annotations

import re
from datetime import datetime

# Только то, в чём лёгкая 4-миллиардная модель не врёт: счёт, перевод, время/дата. Рассуждения — ей нельзя
# (проверено 2026-10-20: «который час в Душанбе, если в Москве 10:00» — страница бреда за 32 с).
SIMPLE = re.compile(
    r"^\s*(?:сколько\s+будет|посчитай\s+\d|переведи|как\s+(?:сказать|будет)\s+по[\s-]|"
    r"который\s+час\??$|сколько\s+времени\??$|какой\s+сегодня\s+день|какое\s+сегодня\s+число)", re.I)
MAX_REPLY = 300

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
        reply = (reply or "").strip()
        if not reply or len(reply) > MAX_REPLY:     # разошлась на страницу — значит, не её вопрос
            return None
        return reply
