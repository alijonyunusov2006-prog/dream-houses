# Локальная модель через Ollama на ПК (RTX 3090). Бесплатно, без внешних сервисов. (копия qabat/bot/llm.py)
# Основная модель занята или упала (рендер забрал видеокарту) → лёгкая → иначе None, и бот зовёт мастера.
import json
import urllib.request


class Ollama:
    def __init__(self, url: str, model: str, fast_model: str = "", timeout: float = 60):
        self.url, self.model, self.fast_model, self.timeout = url.rstrip("/"), model, fast_model, timeout

    def _chat(self, model: str, messages: list[dict], timeout: float) -> str:
        body = json.dumps({"model": model, "messages": messages, "stream": False, "think": False,   # без «размышлений»: иначе 4b-модель молчит 20+ с
                           "options": {"temperature": 0.3, "num_predict": 300}}).encode()
        req = urllib.request.Request(self.url + "/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"]

    def reply(self, system: str, history: list[dict]) -> str | None:
        messages = [{"role": "system", "content": system}] + history
        for model, t in ((self.model, self.timeout), (self.fast_model, self.timeout / 2)):
            if not model:
                continue
            try:
                return self._chat(model, messages, t)
            except Exception:
                continue
        return None
