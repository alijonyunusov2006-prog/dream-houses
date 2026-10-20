from jarviscore.local import LocalBrain, is_simple


def test_simple_questions_detected():
    for t in ("Сколько будет 12 умножить на 8?", "Который час?", "Переведи «спасибо» на таджикский",
              "Как сказать по-английски «дом»?", "Какой сегодня день недели?"):
        assert is_simple(t), t


def test_reasoning_and_work_tasks_are_not_simple():
    for t in ("Сделай список дел", "Открой проект Ашан и проверь чертежи", "Удали старые рендеры",
              "Напиши отчёт по проекту", "Посчитай файлы в папке C:\\Jarvis",
              "Который час в Душанбе, если в Москве 10:00?", "Что такое ипотека?", "Чем отличается ипотека от кредита?"):
        assert not is_simple(t), t


def test_long_rambling_reply_is_rejected():
    class Rambler:
        def reply(self, system, history): return "бред " * 200
    assert LocalBrain(Rambler()).answer("Сколько будет 2+2?") is None


def test_local_brain_calls_ollama_and_falls_back_to_none(monkeypatch):
    calls = []

    class Fake:
        def reply(self, system, history):
            calls.append((system, history))
            return "Будет 96."

    b = LocalBrain(Fake())
    assert b.answer("Сколько будет 12 умножить на 8?") == "Будет 96."
    assert "сэр" in calls[0][0] and calls[0][1][-1]["content"].startswith("Сколько")

    class Down:
        def reply(self, system, history):
            return None

    assert LocalBrain(Down()).answer("Который час?") is None
