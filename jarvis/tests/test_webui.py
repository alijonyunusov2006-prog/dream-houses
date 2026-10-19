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
