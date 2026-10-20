from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import threading

from jarviscore.office import agents_view, load_agents, load_projects, snapshot
from jarviscore.planner import State, Task

AGENTS = Path(__file__).resolve().parents[1] / ".claude" / "agents"


def task(id_, state, agent=None, title="задача", progress="", when=None):
    t = Task(id=id_, title=title, state=state, progress=progress)
    if agent:
        t.checkpoint["agent"] = agent
    if when:
        t.updated_at = when
    return t


def test_all_real_agents_listed_with_russian_names():
    a = load_agents(AGENTS)
    ids = {x["id"] for x in a}
    assert {"jarvis", "archviz", "coach", "secretary", "developer"} <= ids
    assert next(x for x in a if x["id"] == "secretary")["role"] == "Секретарь"
    assert all(x["role"] for x in a)


def test_agent_statuses_work_wait_idle():
    agents = [{"id": "jarvis", "role": "J"}, {"id": "archviz", "role": "A"}, {"id": "developer", "role": "D"},
              {"id": "secretary", "role": "S"}]
    now = datetime.now(timezone.utc)
    tasks = [task("1", State.RUNNING, "archviz", "рендер"), task("2", State.WAITING_HUMAN, "developer", "сайт"),
             task("3", State.DONE, "secretary", "дайджест", "Отчёт: отправлен", now),
             task("4", State.PENDING, "archviz", "второй рендер"), task("5", State.PENDING, None, "новое")]
    v = {r["id"]: r for r in agents_view(agents, tasks, now.astimezone().date())}
    assert v["archviz"]["status"] == "work" and v["archviz"]["task"]["title"] == "рендер"
    assert [q["title"] for q in v["archviz"]["queue"]] == ["второй рендер"]
    assert v["developer"]["status"] == "wait"
    assert v["secretary"]["status"] == "idle" and v["secretary"]["done_today"] == 1
    assert v["secretary"]["last"]["text"] == "Отчёт: отправлен"
    assert v["jarvis"]["status"] == "work"          # разбирает новую задачу без агента
    assert v["jarvis"]["task"]["state_ru"] == "разбираю задание"


def test_unknown_agent_goes_to_jarvis():
    agents = [{"id": "jarvis", "role": "J"}]
    v = agents_view(agents, [task("1", State.RUNNING, "superman")], datetime.now().date())
    assert v[0]["status"] == "work"


def test_projects_parsed_and_secrets_and_english_dropped(tmp_path):
    (tmp_path / "Макет.md").write_text(
        "# Макет\n\n> Печать макета на P1S.\n\n**Где на диске:** `C:\maket`\n**Работали:** 2026-10-01 — 2026-10-18 (5 дн.)\n\n"
        "## На чём остановились\n\nРабота закончена. Файл на флешке.\nпароль от wifi: qwerty12345\n\n## Дни работы\n", encoding="utf-8")
    (tmp_path / "Старое.md").write_text(
        "# Старое\n**Работали:** 2026-08-01\n\n## На чём остановились\n\nMonitor CUDA library installation.\n", encoding="utf-8")
    p = {x["name"]: x for x in load_projects(tmp_path, now=datetime(2026, 10, 21))}
    m = p["Макет"]
    assert m["state"] == "done" and m["last"] == "2026-10-18" and m["days"] == 5
    assert "флешке" in m["next"] and "qwerty" not in m["next"] and "пароль" not in m["next"]
    assert m["summary"] == "Печать макета на P1S." and "maket" in m["where"]
    assert p["Старое"]["state"] == "quiet" and p["Старое"]["next"] == ""
    assert load_projects(tmp_path / "нет") == []


def test_snapshot_shape():
    bot = SimpleNamespace(lock=threading.Lock(), telegram_on=False,
                          ctl=SimpleNamespace(sched=SimpleNamespace(tasks={"1": task("1", State.RUNNING, "archviz")})))
    s = snapshot(bot, AGENTS, None, None)
    assert s["jarvis"]["running"] == 1 and s["projects"] == [] and s["machine"] == {}
    assert next(a for a in s["agents"] if a["id"] == "archviz")["status"] == "work"
