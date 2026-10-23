import os

from jarviscore import app
from jarviscore.bot import load_env


def test_app_module_assembles():
    assert callable(app.main) and app.PORT == 8765


def test_already_running_detects_busy_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); s.listen()
        port = s.getsockname()[1]
        assert app.already_running(port)
    assert not app.already_running(port)


def test_load_env_reads_keys_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.delenv("JV_TEST_A", raising=False)
    monkeypatch.setenv("JV_TEST_B", "уже есть")
    (tmp_path / ".env").write_text("# комментарий\nJV_TEST_A=1\nJV_TEST_B=2\n", encoding="utf-8")
    load_env(tmp_path / ".env")
    assert os.environ["JV_TEST_A"] == "1" and os.environ["JV_TEST_B"] == "уже есть"
