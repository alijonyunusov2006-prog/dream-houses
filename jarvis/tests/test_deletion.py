import json
import subprocess
import sys
from pathlib import Path

import pytest

from jarviscore.deletion import Action, DeletionGuard, Level

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def guard(tmp_path):
    return DeletionGuard(
        state_path=tmp_path / "deletion.json",
        important_globs=["C:/jarvis/brain*", "*.max", "repo:*"],
        ordinary_globs=["C:/jarvis/data/tmp*"],
        allowed_dirs=["C:/jarvis", "C:/Projects"],
        now=Clock(),
    )


def test_classify(guard):
    assert guard.classify("C:/jarvis/brain/10-rules/always.md") is Level.IMPORTANT
    assert guard.classify("C:\\jarvis\\brain") is Level.IMPORTANT
    assert guard.classify("C:/Projects/crm/render.max") is Level.IMPORTANT
    assert guard.classify("C:/Projects/crm/node_modules") is Level.ORDINARY
    assert guard.classify("C:/jarvis/data/tmp/x.wav") is Level.ORDINARY
    assert guard.classify("C:/Windows/System32") is Level.IMPORTANT      # вне разрешённых папок
    assert guard.classify("repo:dream-houses") is Level.IMPORTANT
    assert guard.classify("vercel:dh-os") is Level.IMPORTANT             # не путь — по умолчанию важное


def test_ordinary_needs_two_yes(guard):
    t, cmd = "C:/Projects/crm/node_modules", "rm -r C:/Projects/crm/node_modules"
    assert guard.request(t, command=cmd).action is Action.ASK_CONFIRM
    assert guard.confirm(t, command=cmd).action is Action.ASK_CONFIRM
    assert guard.consume_unlock(cmd) is None                              # одного «да» мало
    out = guard.confirm(t, command=cmd)
    assert out.action is Action.UNLOCKED and not out.backup_required
    assert guard.consume_unlock(cmd) is not None
    assert guard.consume_unlock(cmd) is None                              # разрешение одноразовое


def test_important_refuses_twice_then_deletes_on_third(guard):
    t, cmd = "C:/jarvis/brain/old", "rm -r C:/jarvis/brain/old"
    first = guard.request(t, command=cmd, where="C:\\jarvis\\brain\\old")
    assert first.action is Action.SELF_SERVICE and "удалите сами" in first.message and "C:\\jarvis\\brain\\old" in first.message
    assert guard.request(t, command=cmd).action is Action.SELF_SERVICE
    assert guard.consume_unlock(cmd) is None
    third = guard.request(t, command=cmd)
    assert third.action is Action.UNLOCKED and third.backup_required
    assert guard.consume_unlock(cmd) is not None


def test_informed_phrase_unlocks_from_second_time(guard):
    t = "repo:old-site"
    phrase = "Я понимаю, что это важная вещь, но я тебе разрешаю удалить"
    assert guard.request(t, owner_text=phrase).action is Action.SELF_SERVICE   # первый раз — всё равно нет
    assert guard.request(t, owner_text=phrase).action is Action.UNLOCKED       # второй раз с фразой — да


def test_yes_on_important_is_just_another_request(guard):
    t = "C:/Projects/a/house.max"
    guard.request(t)
    assert guard.confirm(t).action is Action.SELF_SERVICE
    assert guard.confirm(t).action is Action.UNLOCKED


def test_counter_resets_after_window(guard):
    t = "C:/jarvis/brain/x"
    guard.request(t)
    guard.request(t)
    guard.now.t += 25 * 3600                                               # прошли сутки
    assert guard.request(t).action is Action.SELF_SERVICE
    assert guard.request(t).count == 2


def test_unlock_expires(guard):
    t, cmd = "C:/jarvis/brain/x", "rm C:/jarvis/brain/x"
    for _ in range(3):
        guard.request(t, command=cmd)
    guard.now.t += 16 * 60
    assert guard.consume_unlock(cmd) is None


def test_hook_allows_only_the_unlocked_command(tmp_path):
    state = ROOT / "data" / "deletion.json"
    backup = state.read_text(encoding="utf-8") if state.exists() else None
    try:
        g = DeletionGuard.from_allowlist(ROOT / "config" / "allowlist.toml", state, root=ROOT)
        cmd = "rm -r C:/jarvis/data/tmp/old-audio"
        g.request("C:/jarvis/data/tmp/old-audio", command=cmd)
        g.confirm("C:/jarvis/data/tmp/old-audio", command=cmd)
        g.confirm("C:/jarvis/data/tmp/old-audio", command=cmd)
        hook = ROOT / "core" / "jarviscore" / "hooks.py"

        def run(c):
            p = subprocess.run([sys.executable, str(hook), "pre"], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": c}}),
                               capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), timeout=30)
            return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]

        assert run("rm -r C:/jarvis/brain") == "ask"                      # чужая команда — как обычно, спросить
        assert run(cmd) == "allow"                                         # разрешённая — проходит
        assert run(cmd) == "ask"                                           # второй раз — снова спросить
    finally:
        if backup is None:
            state.unlink(missing_ok=True)
        else:
            state.write_text(backup, encoding="utf-8")
