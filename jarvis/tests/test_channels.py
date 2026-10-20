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


# --- голосовые ответы в Телеграм (2026-10-21) ---
def test_voice_follows_text_but_not_for_service_lines(tmp_path):
    import threading
    from jarviscore.channels import Broadcast, VoiceOut, WebFeed

    class TG:
        def __init__(self):
            self.texts, self.voices, self.done = [], [], threading.Event()
        def send(self, chat, text, reply_to=None):
            self.texts.append(text); return {"message_id": len(self.texts)}
        def send_voice(self, chat, ogg, reply_to=None):
            self.voices.append(ogg); self.done.set(); return {"message_id": 99}

    tg = TG()
    feed = WebFeed(tmp_path / "f.jsonl")
    bc = Broadcast(feed, tg, 42)
    spoken = []
    bc.voice = VoiceOut(tg, 42, speech=lambda mid: spoken.append(mid) or b"WAV", to_ogg=lambda wav: b"OGG" + wav)
    bc.send(42, "🎙 Расслышал: привет")
    bc.send(42, "Принял, задача №5. Сейчас скажу, что понял.")
    bc.send(42, "Добрый вечер, сэр.")
    assert tg.done.wait(5)
    bc.voice.stop()
    assert tg.voices == [b"OGGWAV"] and len(spoken) == 1 and len(tg.texts) == 3


def test_voice_failure_never_breaks_text(tmp_path):
    from jarviscore.channels import Broadcast, VoiceOut, WebFeed

    class TG:
        def __init__(self): self.texts = []
        def send(self, chat, text, reply_to=None):
            self.texts.append(text); return {"message_id": 1}
        def send_voice(self, *a, **k): raise RuntimeError("сеть")

    tg = TG()
    bc = Broadcast(WebFeed(tmp_path / "f.jsonl"), tg, 42)
    bc.voice = VoiceOut(tg, 42, speech=lambda mid: None, to_ogg=lambda w: w)   # голос недоступен
    bc.send(42, "Добрый вечер, сэр.")
    bc.voice.stop()
    assert tg.texts == ["Добрый вечер, сэр."]


def test_telegram_send_voice_is_multipart(monkeypatch):
    from jarviscore import telegram as T
    seen = {}

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"ok": true, "result": {"message_id": 7}}'

    def fake(req, timeout=None):
        seen["ct"], seen["body"], seen["url"] = req.get_header("Content-type"), req.data, req.full_url
        return R()
    monkeypatch.setattr(T.urllib.request, "urlopen", fake)
    res = T.Telegram("123:abc").send_voice(42, b"OGGDATA")
    assert res["message_id"] == 7 and seen["url"].endswith("/sendVoice")
    assert "multipart/form-data" in seen["ct"] and b"OGGDATA" in seen["body"] and b'name="chat_id"' in seen["body"]
