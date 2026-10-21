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


@pytest.mark.parametrize("text,kind", [
    ("стоп-кадр из рендера сохрани", "work"), ("Хватит ли места на диске?", "question"),
    ("отменить встречу завтра", "work"), ("Отчёт по Хаджи Акбар подготовь", "work"),
    ("Статус принтера проверь", "work"), ("Что сделано по проекту Ашан?", "question"),
    ("Справка для банка сделай", "work"), ("Покажи офис COLORADO 3D в рендере", "work"),
    ("повтори рендер с другим светом", "work"), ("покажи офис", "office"), ("отчёт", "status"),
])
def test_no_false_talk_on_real_work(text, kind):
    assert classify(text).kind == kind


def test_number_only_with_word_or_alone():
    assert classify("Стоп, рендер 4К").number is None
    assert classify("отмени 7").number == "7"


# --- «стоп» в любой форме (владелец 21.10: «говорю стоп — не слушается, заводит №14, №15») ---
@pytest.mark.parametrize("text,number", [
    ("да стоп же", None), ("Стоп, я сказал!", None), ("стоп сучка", None), ("ну стоп", None),
    ("Джарвис стоп", None), ("хватит уже", None), ("остановись", None), ("прекрати", None),
    ("отменяю 14", "14"), ("отменяю задачу 15", "15"), ("отмени задачу номер 16", "16"),
    ("слушай, не надо", None), ("я сказал стоп", None),
])
def test_stop_in_any_form(text, number):
    i = classify(text)
    assert i.kind == "stop" and i.number == number, (text, i)


@pytest.mark.parametrize("text", ["отмени всё", "отмени все задачи", "стоп всё", "отменяю все"])
def test_cancel_all(text):
    assert classify(text).kind == "stop_all"


@pytest.mark.parametrize("text", ["замолчи", "тихо", "помолчи", "не говори", "заткнись"])
def test_hush(text):
    assert classify(text).kind == "hush"


def test_rude_words_alone_are_not_tasks():
    assert classify("сучка").kind in ("noise", "rude") and classify("ты тупой").kind == "rude"
