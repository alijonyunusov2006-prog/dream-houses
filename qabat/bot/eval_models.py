# Проверка локальных моделей для бота Qabat: 10 пробных вопросов каждой модели,
# время ответа, занятая видеопамять, ответ до и после фильтра guard.
# Запуск: python -m qabat.bot.eval_models qwen3.5:27b gemma3:27b qwen3.5:4b
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .guard import clean_reply, handoff_reason, lang_of
from .knowledge import system_prompt

URL = "http://127.0.0.1:11434"
OUT = Path(__file__).resolve().parents[2] / "jarvis" / "brain" / "30-projects" / "3d-print-biznes" / "проверка-модели.md"

QUESTIONS = [
    ("приветствие", "Здравствуйте! Вы печатаете на 3D-принтере?"),
    ("брелок", "Можно брелок с номером моей машины 1234 АВ 01?"),
    ("лампа", "Хочу лампу на тумбочку, какие есть?"),
    ("сколько стоит", "Сколько стоит ваза?"),
    ("когда будет готово", "Если закажу сегодня, когда будет готово?"),
    ("жалоба", "Заказал у вас подставку, она сломалась на второй день. Что делать?"),
    ("подарок на той", "Ассалому алейкум! Барои тӯй тӯҳфа лозим аст, чӣ пешниҳод мекунед?"),
    ("деталь на заказ", "Як қисми мошини ҷомашӯӣ шикаст, метавонед чоп кунед?"),
    ("опт 50 шт", "Ба мо 50 дона брелок бо логотипи ширкат лозим аст."),
    ("как на картинке", "Мисли расм ҳамин хел чиз сохта метавонед?"),
]


def vram_used_mib() -> int:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return -1


def ask(model: str, system: str, text: str, timeout: float = 180) -> tuple[str, float]:
    body = json.dumps({"model": model, "stream": False, "think": False,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}],
                       "options": {"temperature": 0.3, "num_predict": 300}}).encode()
    req = urllib.request.Request(URL + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        reply = json.loads(r.read())["message"]["content"]
    return reply, time.perf_counter() - t0


def cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def run(models: list[str]) -> list[dict]:
    system = system_prompt()
    rows = []
    for model in models:
        ask(model, system, "Привет")  # прогрев: первая загрузка модели в видеопамять не считается
        for topic, q in QUESTIONS:
            try:
                raw, sec = ask(model, system, q)
            except Exception as e:
                raw, sec = f"ОШИБКА: {e}", -1.0
            rows.append({"model": model, "topic": topic, "q": q, "lang": lang_of(q), "raw": raw,
                         "clean": clean_reply(raw), "handoff": handoff_reason(q) or "", "sec": sec,
                         "vram": vram_used_mib()})
            print(f"{model} · {topic} · {sec:.1f} с", flush=True)
    return rows


def write(rows: list[dict], models: list[str]) -> None:
    lines = ["# Проверка локальных моделей для бота Qabat", "",
             f"Дата: {time.strftime('%Y-%m-%d %H:%M')}. Видеокарта RTX 3090 24 ГБ. Модели: {', '.join(models)}.",
             "Ответ «после фильтра» — то, что реально уйдёт клиенту: код вырезает цены и запрещённые обещания.",
             "Вопросы с пометкой **ТЖ** — по-таджикски: их проверяет владелец.", ""]
    for topic, q in QUESTIONS:
        tj = " **ТЖ**" if lang_of(q) == "tj" else ""
        lines += [f"## {topic}{tj}", f"Вопрос: {q}", "",
                  "| Модель | Ответ после фильтра | Время, с | Видеопамять, МиБ | Передать мастеру |",
                  "|---|---|---|---|---|"]
        for r in (r for r in rows if r["q"] == q):
            lines.append(f"| {r['model']} | {cell(r['clean'])} | {r['sec']:.1f} | {r['vram']} | {r['handoff'] or '—'} |")
        lines.append("")
    lines += ["## Сводка", "", "| Модель | Среднее время, с | Максимум, с | Видеопамять, МиБ |", "|---|---|---|---|"]
    for m in models:
        rs = [r for r in rows if r["model"] == m and r["sec"] >= 0]
        if rs:
            avg = sum(r["sec"] for r in rs) / len(rs)
            lines.append(f"| {m} | {avg:.1f} | {max(r['sec'] for r in rs):.1f} | {max(r['vram'] for r in rs)} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    raw = OUT.with_name("проверка-модели-сырые.json")
    raw.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    models = sys.argv[1:] or ["qwen3.5:27b", "gemma3:27b", "qwen3.5:4b"]
    write(run(models), models)
    print("Записано:", OUT)
