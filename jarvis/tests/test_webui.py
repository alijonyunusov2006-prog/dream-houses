import json
import socket
import urllib.error
import urllib.request

import pytest

from jarviscore.bot import JarvisBot
from jarviscore.channels import Broadcast, WebFeed
from jarviscore.controller import Controller
from jarviscore.planner import Scheduler
from jarviscore.webui import JarvisWeb, serve


class NoClaude:
    def understand(self, t):
        raise AssertionError("в этих тестах исполнитель не запускается")


@pytest.fixture
def web(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    feed = WebFeed()
    ctl = Controller(Scheduler(), tmp_path / "tasks.json")
    bot = JarvisBot(Broadcast(feed), ctl, NoClaude(), None, owner_chat=0,
                    ideas_dir=tmp_path / "ideas", tmp_dir=tmp_path / "tmp")
    server = serve(JarvisWeb(bot, feed, tmp_path / "tmp"), port)
    yield f"http://127.0.0.1:{port}", ctl, port
    server.shutdown()


def call(url, data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_page_opens(web):
    base, _, _ = web
    code, body = call(base + "/")
    assert code == 200 and "JARVIS" in body.decode("utf-8")


def test_message_from_window_becomes_task_and_shows_in_feed(web):
    base, ctl, _ = web
    code, _ = call(base + "/api/send", {"text": "Сделай список дел"}, {"X-Jarvis": "1"})
    assert code == 200 and ctl.sched.tasks["1"].title == "Сделай список дел"
    state = json.loads(call(base + "/api/state?after=0")[1])
    whos = [m["who"] for m in state["feed"]]
    assert whos == ["owner", "jarvis"] and state["tasks"][0]["state_ru"] == "в очереди"
    assert state["tasks"][0]["stage"] == 0
    assert state["stats"] == {"open": 1, "waiting": 0, "running": 0, "done_today": 0}


def test_window_scripts_are_served_but_nothing_else(web):
    base, _, _ = web
    code, body = call(base + "/reactor.js")
    assert code == 200 and b"Reactor" in body
    for bad in ("/../bot.js", "/..%2fbot.js", "/web/reactor.js", "/nope.js", "/index.html.js"):
        assert call(base + bad)[0] == 404


class SaySTT:
    def __init__(self, *phrases):
        self.phrases = list(phrases)

    def transcribe(self, path):
        return self.phrases.pop(0)


def make_app(tmp_path, *phrases):
    feed = WebFeed()
    ctl = Controller(Scheduler(), tmp_path / "tasks.json")
    bot = JarvisBot(Broadcast(feed), ctl, NoClaude(), SaySTT(*phrases), owner_chat=0,
                    ideas_dir=tmp_path / "ideas", tmp_dir=tmp_path / "tmp")
    return JarvisWeb(bot, feed, tmp_path / "tmp"), ctl, feed


def test_hear_without_wake_word_is_dropped_and_not_logged(tmp_path):
    app, ctl, feed = make_app(tmp_path, "мы обсуждали проект Ашан с клиентом")
    assert app.hear(b"wav") == {"heard": False}
    assert feed.since(0) == [] and ctl.sched.tasks == {}
    assert not list((tmp_path / "tmp").glob("*"))          # запись удалена


def test_hear_with_wake_word_runs_command(tmp_path):
    app, ctl, feed = make_app(tmp_path, "Джарвис, сделай список дел")
    assert app.hear(b"wav")["text"] == "сделай список дел"
    assert ctl.sched.tasks["1"].title == "сделай список дел"


def test_bare_wake_word_arms_for_next_phrase_only_briefly(tmp_path):
    app, ctl, feed = make_app(tmp_path, "Джарвис!", "открой проект Ашан", "Джарвис", "и ещё кое-что")
    assert app.hear(b"wav", now=100.0) == {"heard": True, "armed": True}
    assert "Слушаю" in feed.since(0)[-1]["text"]
    assert app.hear(b"wav", now=105.0)["text"] == "открой проект Ашан"
    app.hear(b"wav", now=200.0)
    assert app.hear(b"wav", now=260.0) == {"heard": False}       # ожидание истекло


def test_jarvis_reply_is_spoken_by_voice_service_and_cached(tmp_path):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading as th

    calls = []

    class FakeTTS(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = b"RIFF-voice"
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)

    srv = HTTPServer(("127.0.0.1", 0), FakeTTS)
    th.Thread(target=srv.serve_forever, daemon=True).start()
    app, ctl, feed = make_app(tmp_path)
    app.tts_url = f"http://127.0.0.1:{srv.server_address[1]}"
    owner_id = feed.add_owner("привет")
    jid = feed.send(0, "Слушаю, сэр.")["message_id"]
    assert app.speech(owner_id) is None                      # озвучиваем только ответы JARVIS
    assert app.speech(jid) == b"RIFF-voice"
    assert app.speech(jid) == b"RIFF-voice" and len(calls) == 1   # второй раз — из кэша
    assert calls[0]["text"] == "Слушаю, сэр."
    srv.shutdown()


def test_voice_service_down_is_not_an_error(tmp_path):
    app, ctl, feed = make_app(tmp_path)
    app.tts_url = "http://127.0.0.1:9"                       # никто не слушает
    jid = feed.send(0, "Добрый вечер, сэр.")["message_id"]
    assert app.speech(jid) is None


def test_pill_endpoint_calls_opener_only_with_header(web):
    base, _, _ = web
    assert call(base + "/api/pill", {}, {"X-Jarvis": "1"})[0] == 200
    assert call(base + "/api/pill", {})[0] == 403


def test_post_without_jarvis_header_is_refused(web):
    base, ctl, _ = web
    code, _ = call(base + "/api/send", {"text": "удали всё"})        # так могла бы попытаться чужая страница
    assert code == 403 and ctl.sched.tasks == {}


def test_foreign_host_header_is_refused(web):
    base, ctl, port = web
    code, _ = call(base + "/api/state", headers={"Host": f"evil.example:{port}"})
    assert code == 403


def test_empty_message_is_rejected(web):
    base, _, _ = web
    code, _ = call(base + "/api/send", {"text": "   "}, {"X-Jarvis": "1"})
    assert code == 400


def test_office_uses_local_3d_library_not_internet(web):
    base, _, _ = web
    req = urllib.request.Request(base + "/office")
    with urllib.request.urlopen(req, timeout=10) as r:
        body, csp = r.read(), r.headers.get("Content-Security-Policy", "")
    assert b"cdn.jsdelivr.net/npm/three" not in body and b"/vendor/three/build/three.module.js" in body
    assert "jsdelivr" not in csp
    code, body = call(base + "/vendor/three/build/three.module.js")
    assert code == 200 and b"REVISION" in body
    code, _ = call(base + "/vendor/three/../../webui.py")
    assert code == 404
    code, data = call(base + "/api/office")
    assert code == 200 and b'"agents"' in data


def test_every_3d_module_the_office_imports_is_on_this_pc():
    """Офис импортирует модули three — каждый (и всё, что они тянут дальше) должен лежать в web/vendor/three."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    vendor = root / "core" / "jarviscore" / "web" / "vendor" / "three"
    page = (root / "docs" / "office3d" / "index.html").read_text(encoding="utf-8")
    todo = [vendor / "examples" / "jsm" / m for m in re.findall(r"from ['\"]three/addons/([^'\"]+)['\"]", page)]
    seen = set()
    while todo:
        f = todo.pop().resolve()
        if f in seen:
            continue
        assert f.is_file(), f"нет модуля {f.relative_to(vendor)}"
        seen.add(f)
        for rel in re.findall(r"from ['\"](\.{1,2}/[^'\"]+)['\"]", f.read_text(encoding="utf-8")):
            todo.append(f.parent / rel)
    assert len(seen) >= 8
