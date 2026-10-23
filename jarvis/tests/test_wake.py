import pytest

from jarviscore.wake import find_wake, is_greeting


@pytest.mark.parametrize("text, rest", [
    ("Джарвис, я дома", "я дома"),
    ("джарвиз сделай список дел", "сделай список дел"),
    ("Эй, Джарвис! Сколько места на диске?", "Сколько места на диске?"),
    ("Jarvis, привет", "привет"),
    ("Жарвис открой почту", "открой почту"),
    ("Джарвис.", ""),
])
def test_wake_word_found_and_command_extracted(text, rest):
    found, got = find_wake(text)
    assert found and got == rest


@pytest.mark.parametrize("text", [
    "сделай список дел",
    "мы обсуждали Джарвиса вчера с клиентом и решили",     # имя в середине обычного разговора — не зов
    "",
    "   ",
])
def test_no_wake_word_means_ignore(text):
    assert find_wake(text) == (False, "")


@pytest.mark.parametrize("text", ["я дома", "Привет", "доброе утро", "я вернулся", "что нового?", "Как дела?"])
def test_greetings_trigger_briefing(text):
    assert is_greeting(text)


@pytest.mark.parametrize("text", ["сделай список дел", "удали старые рендеры", "я дома сделай отчёт по проекту Ашан"])
def test_tasks_are_not_greetings(text):
    assert not is_greeting(text)
