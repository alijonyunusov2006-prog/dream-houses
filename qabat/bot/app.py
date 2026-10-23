# Логика бота Qabat: клиент пишет боту → копия в тему клиента в группе владельца → ответ модели
# (после проверки guard) → клиенту. Владелец пишет в теме → сообщение уходит клиенту, бот молчит до /bot.
from .guard import clean_reply, handoff_reason, lang_of

HANDOFF_TEXT = {
    "ru": "Спасибо! Передал ваш вопрос мастеру, он ответит здесь.",
    # таджикский текст — на проверку владельцу
    "tj": "Ташаккур! Саволи шуморо ба устод супоридам, ӯ ҳамин ҷо ҷавоб медиҳад.",
}
GREETING = "Салом! Это Qabat — 3D-печать в Душанбе. Напишите, что хотите напечатать, — мастер ответит с ценой и сроком."


class QabatBot:
    def __init__(self, tg, llm, store, owner_chat: int | None, system: str, prices_on: bool = False, greeting: str = GREETING):
        self.tg, self.llm, self.store = tg, llm, store
        self.owner_chat, self.system, self.prices_on, self.greeting = owner_chat, system, prices_on, greeting

    def handle(self, update: dict):
        msg = update.get("message")
        if not msg or msg.get("from", {}).get("is_bot"):
            return
        chat = msg["chat"]
        text = (msg.get("text") or "").strip()
        if chat["type"] != "private":
            if text.startswith("/id"):  # настройка: узнать номер группы для QABAT_OWNER_CHAT_ID
                self.tg.send(chat["id"], f"Номер этой группы: {chat['id']}", msg.get("message_thread_id"))
            elif chat["id"] == self.owner_chat and msg.get("message_thread_id"):
                self.on_owner(msg, text)
            return
        self.on_client(msg, text)

    # --- клиент ---
    def _topic(self, c: dict) -> int | None:
        if self.owner_chat is None:
            return None
        if not c.get("topic_id"):
            c = self.store.save_client(c["user_id"], topic_id=self.tg.create_topic(self.owner_chat, f"{c['name']} · {c['user_id']}"))
        return c["topic_id"]

    def on_client(self, msg: dict, text: str):
        u = msg["from"]
        uid = u["id"]
        name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or "Клиент"
        if u.get("username"):
            name += f" @{u['username']}"
        c = self.store.client(uid) or self.store.save_client(uid, name=name)
        topic = self._topic(c)
        c = self.store.client(uid)
        if self.owner_chat is not None:
            self.tg.copy(self.owner_chat, uid, msg["message_id"], topic)
        if text == "/start":
            self.tg.send(uid, self.greeting)
            return
        text = text or (msg.get("caption") or "").strip()
        if text:
            c = self.store.save_client(uid, lang=lang_of(text))
            self.store.add(uid, "user", text)
        if c["mode"] == "owner":
            return
        has_media = any(k in msg for k in ("photo", "voice", "audio", "video", "document", "video_note"))
        reason = "фото или файл от клиента" if has_media else handoff_reason(text)
        if not text and not has_media:
            return
        if reason:
            return self.handoff(c, reason, topic)
        raw = self.llm.reply(self.system, self.store.history(uid))
        if raw is None:
            return self.handoff(c, "модель не ответила (ПК занят или выключена Ollama)", topic)
        reply = clean_reply(raw, self.prices_on)
        self.tg.send(uid, reply)
        self.store.add(uid, "assistant", reply)
        if topic:
            self.tg.send(self.owner_chat, "Бот ответил: " + reply, topic)

    def handoff(self, c: dict, reason: str, topic):
        self.store.save_client(c["user_id"], mode="owner")
        self.tg.send(c["user_id"], HANDOFF_TEXT.get(c.get("lang"), HANDOFF_TEXT["ru"]))
        if topic:
            self.tg.send(self.owner_chat, f"Нужен мастер: {reason}. Ответьте в этой теме — сообщение уйдёт клиенту. "
                                          f"/bot — снова отвечает бот.", topic)

    # --- владелец ---
    def on_owner(self, msg: dict, text: str):
        c = self.store.by_topic(msg["message_thread_id"])
        if not c:
            return
        if text == "/bot":
            self.store.save_client(c["user_id"], mode="bot")
            self.tg.send(self.owner_chat, "Бот снова отвечает этому клиенту.", c["topic_id"])
            return
        if text == "/me":
            self.store.save_client(c["user_id"], mode="owner")
            self.tg.send(self.owner_chat, "Бот молчит, отвечаете вы.", c["topic_id"])
            return
        if text.startswith("/"):
            return
        self.tg.copy(c["user_id"], self.owner_chat, msg["message_id"])
        self.store.save_client(c["user_id"], mode="owner")
        if text:
            self.store.add(c["user_id"], "assistant", text)
