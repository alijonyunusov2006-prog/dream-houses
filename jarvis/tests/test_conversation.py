import pytest

from jarviscore.conversation import classify


@pytest.mark.parametrize("text,kind", [
    ("ты здесь?", "presence"), ("Ты меня слышишь", "presence"), ("алло", "presence"),
    ("спасибо", "thanks"), ("Молодец!", "thanks"),
    ("повтори", "repeat"), ("ещё раз", "repeat"), ("что ты сказал?", "repeat"),
    ("что ты сейчас делаешь?", "status"), ("какие задачи?", "status"), ("что сделал сегодня", "status"),
    ("что ты умеешь?", "abilities"), ("помощь", "abilities"),
    ("не надо", "stop"), ("Стоп", "stop"), ("Не надо, номер 14, слушай, слушай меня.", "stop"), ("отмени 7", "stop"),
    ("Конец.", "noise"), ("...", "noise"), ("эээ", "noise"),
    ("сколько файлов в папке образцы?", "question"), ("Как настроить свет в Короне?", "question"),
    ("Где лежит проект Ашан", "question"),
    ("Сделай рендер гостиной", "work"), ("найди чертежи Ашана и проверь размеры", "work"),
    ("Посчитай, сколько файлов в папке образцы", "work"), ("Можешь вот как-то ты учишься, я дома.", "work"),
])
def test_classify(text, kind):
    assert classify(text).kind == kind


def test_stop_reads_number():
    assert classify("Не надо, номер 14, слушай").number == "14"
    assert classify("отмени задачу №7").number == "7"
    assert classify("не надо").number is None
