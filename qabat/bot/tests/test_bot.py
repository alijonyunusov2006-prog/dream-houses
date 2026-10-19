# Проверка бота без интернета: поддельные Telegram и модель.  Запуск: python -m pytest qabat/bot/tests -q
from qabat.bot.app import QabatBot, HANDOFF_TEXT
from qabat.bot.guard import clean_reply, handoff_reason, lang_of, PRICE_STUB
from qabat.bot.knowledge import system_prompt, load_kit
from qabat.bot.store import Store

OWNER = -100500


class FakeTG:
    def __init__(self):
        self.sent, self.copies, self.topics = [], [], 0

    def send(self, chat, text, thread=None):
        self.sent.append((chat, text, thread))

    def copy(self, to, frm, mid, thread=None):
        self.copies.append((to, frm, mid, thread))

    def create_topic(self, chat, name):
        self.topics += 1
        return 1000 + self.topics


class FakeLLM:
    def __init__(self, answer="Да, сделаем брелок. Какой номер и цвет?"):
        self.answer, self.calls = answer, 0

    def reply(self, system, history):
        self.calls += 1
        return self.answer


def client(text, uid=7, mid=1, **extra):
    m = {"message_id": mid, "from": {"id": uid, "first_name": "Фаррух"}, "chat": {"id": uid, "type": "private"}}
    if text is not None:
        m["text"] = text
    m.update(extra)
    return {"message": m}


def owner(text, topic, mid=50):
    return {"message": {"message_id": mid, "from": {"id": 1, "first_name": "Алижон"},
                        "chat": {"id": OWNER, "type": "supergroup"}, "message_thread_id": topic, "text": text}}


def make(answer=None):
    tg, llm = FakeTG(), FakeLLM(answer) if answer is not None else FakeLLM()
    return QabatBot(tg, llm, Store(), OWNER, "system"), tg, llm


def test_client_gets_model_answer_and_owner_sees_topic():
    bot, tg, llm = make()
    bot.handle(client("Хочу брелок с номером машины"))
    assert llm.calls == 1
    assert (7, "Да, сделаем брелок. Какой номер и цвет?", None) in tg.sent
    assert tg.copies == [(OWNER, 7, 1, 1001)]
    assert any(c == OWNER and t == 1001 and txt.startswith("Бот ответил") for c, txt, t in tg.sent)


def test_one_topic_per_client():
    bot, tg, _ = make()
    bot.handle(client("Салом", mid=1))
    bot.handle(client("Есть лампы?", mid=2))
    assert tg.topics == 1


def test_price_is_removed_while_prices_paused():
    bot, tg, _ = make("Брелок стоит 40 сомони. Обычно готовим за 1 день.")
    bot.handle(client("Сколько стоит брелок?"))
    reply = [t for c, t, _ in tg.sent if c == 7][0]
    assert "40" not in reply and "сомони" not in reply
    assert PRICE_STUB in reply and "1 день" in reply


def test_complaint_goes_to_owner_without_model():
    bot, tg, llm = make()
    bot.handle(client("Это жалоба: брелок сломался сразу"))
    assert llm.calls == 0
    assert (7, HANDOFF_TEXT["ru"], None) in tg.sent
    assert any("Нужен мастер: жалоба" in t for c, t, _ in tg.sent if c == OWNER)


def test_photo_goes_to_owner():
    bot, tg, llm = make()
    bot.handle(client(None, photo=[{"file_id": "x"}], caption="вот такое"))
    assert llm.calls == 0 and any("фото" in t for c, t, _ in tg.sent if c == OWNER)


def test_owner_reply_goes_to_client_and_bot_stays_silent_until_bot_command():
    bot, tg, llm = make()
    bot.handle(client("Хочу брелок", mid=1))
    bot.handle(owner("Здравствуйте, это мастер", 1001, mid=60))
    assert (7, OWNER, 60, None) in tg.copies
    bot.handle(client("А цвет красный есть?", mid=2))
    assert llm.calls == 1  # бот молчит — отвечает мастер
    bot.handle(owner("/bot", 1001))
    bot.handle(client("А синий?", mid=3))
    assert llm.calls == 2


def test_tajik_client_gets_tajik_handoff():
    bot, tg, _ = make()
    bot.handle(client("Шикоят дорам: брелоки ман шикаст, ҳозир чӣ кунам?"))
    assert (7, HANDOFF_TEXT["tj"], None) in tg.sent


def test_model_down_hands_off():
    bot, tg, _ = make()
    bot.llm.reply = lambda s, h: None
    bot.handle(client("Есть ночник?"))
    assert any("модель не ответила" in t for c, t, _ in tg.sent if c == OWNER)


def test_group_id_command():
    bot, tg, _ = make()
    bot.handle({"message": {"message_id": 1, "from": {"id": 1}, "chat": {"id": -42, "type": "supergroup"}, "text": "/id"}})
    assert tg.sent == [(-42, "Номер этой группы: -42", None)]


def test_guard_rules():
    # случай из проверки на ПК 2026-10-19: модель ответила сама вместо мастера
    assert handoff_reason("Заказал у вас подставку, она сломалась на второй день. Что делать?") == "жалоба"
    assert handoff_reason("нужно 50 шт на той") == "опт"
    assert handoff_reason("Хочу лампу") is None
    assert lang_of("Ман брелок мехоҳам") == "tj"
    assert "готово" not in clean_reply("Ваш заказ готово. Заберите завтра.").lower()


def test_system_prompt_has_catalog_but_no_prices():
    p = system_prompt(load_kit())
    assert "QB-01" in p and "Брелок «Номер машины»" in p
    assert "сомони" not in p.split("Каталог:")[1]
    assert "Цены не называй" in p
