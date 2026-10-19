from jarviscore.channels import Broadcast, WebFeed


class FakeTG:
    def __init__(self, fail=False):
        self.sent, self.fail, self._mid = [], fail, 500

    def send(self, chat_id, text, reply_to=None):
        if self.fail:
            raise ConnectionError("нет сети")
        self._mid += 1
        self.sent.append((chat_id, text, reply_to))
        return {"message_id": self._mid}


def test_feed_numbers_messages_and_survives_restart(tmp_path):
    f = WebFeed(tmp_path / "feed.jsonl")
    f.add_owner("привет")
    assert f.send(0, "здравствуйте")["message_id"] == 2
    f2 = WebFeed(tmp_path / "feed.jsonl")
    assert [i["who"] for i in f2.since(0)] == ["owner", "jarvis"]
    assert f2.add_owner("ещё") == 3
    assert [i["text"] for i in f2.since(2)] == ["ещё"]


def test_broadcast_writes_to_window_and_telegram_and_maps_replies():
    web, tg = WebFeed(), FakeTG()
    b = Broadcast(web, tg, tg_chat=7)
    q = b.send(7, "Вопрос?")["message_id"]
    tg_id = tg.sent[-1]
    assert web.since(0)[0]["text"] == "Вопрос?" and tg_id[0] == 7
    assert b.web_of(501) == q                    # ответ из Telegram находит вопрос окна
    b.send(7, "ответ на вопрос", reply_to=q)
    assert tg.sent[-1][2] == 501                 # в Telegram — ответом на тот же вопрос


def test_telegram_failure_does_not_lose_window_message():
    web = WebFeed()
    b = Broadcast(web, FakeTG(fail=True), tg_chat=7)
    assert b.send(7, "важное")["message_id"] == 1
    assert web.since(0)[0]["text"] == "важное"


def test_window_only_mode_without_telegram():
    web = WebFeed()
    b = Broadcast(web)
    b.send(0, "только окно")
    assert web.since(0)[0]["text"] == "только окно"


def test_web_voice_file_is_moved_not_downloaded(tmp_path):
    src = tmp_path / "rec.webm"
    src.write_bytes(b"x")
    b = Broadcast(WebFeed())
    out = b.download(f"web:{src}", tmp_path / "tmp" / "voice.webm")
    assert out.read_bytes() == b"x" and not src.exists()
