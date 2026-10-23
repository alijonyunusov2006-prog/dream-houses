from jarviscore.memory import is_recall, search


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_recall_phrases():
    for t in ("вспомни, что мы решили про Ашан", "Что мы решили про цены Qabat?", "найди в памяти голос",
              "где лежит DWG офиса"):
        assert is_recall(t)
    for t in ("сделай список дел", "удали рендеры", "я дома"):
        assert not is_recall(t)


def test_search_finds_relevant_lines_ranked(tmp_path):
    write(tmp_path / "a" / "decided.md", "| 2026-10-05 | Цены Qabat — на паузе, решает владелец |\n| другое | нет |\n")
    write(tmp_path / "b" / "ashan.md", "# Ашан\nАльбом 6 листов, 3D Three.js\nЦены не обсуждали\n")
    write(tmp_path / "b" / "skip.txt", "Цены Qabat в txt не ищем")
    hits = search("что мы решили про цены Qabat", [tmp_path / "a", tmp_path / "b"])
    assert hits and hits[0].file.name == "decided.md" and "паузе" in hits[0].line
    assert all(h.file.suffix == ".md" for h in hits)


def test_search_ignores_stopwords_and_empty(tmp_path):
    write(tmp_path / "x.md", "что мы про это\n")
    assert search("что мы решили про", [tmp_path]) == []
    assert search("", [tmp_path]) == []


def test_secrets_never_returned_and_service_dirs_skipped(tmp_path):
    write(tmp_path / "keys.md", "Пароль от бота Qabat: qwerty123\nТокен Qabat = 7777:AAAAAAAAAAAAAAAAAAAAAAAAA\n")
    write(tmp_path / ".obsidian" / "x.md", "Qabat настройки обсидиана\n")
    write(tmp_path / "ok.md", "Qabat — бот для клиентов\n")
    hits = search("Qabat", [tmp_path])
    assert [h.file.name for h in hits] == ["ok.md"]


def test_word_forms_match_by_stem(tmp_path):
    write(tmp_path / "x.md", "Голос Джарвиса делаем через Qwen3-TTS\n")
    assert search("какой голос у джарвиса", [tmp_path])[0].line.startswith("Голос")


def test_answer_is_plain_text_without_tables_and_file_names(tmp_path):
    from jarviscore.memory import answer
    (tmp_path / "decided.md").write_text(
        "| 2026-10-20 | **Голос JARVIS — ESpeech** (эталон `obrazcy/x.wav`). Выбрал [[голос|на слух]] | голос |\n", encoding="utf-8")
    a = answer("вспомни, что решили про голос", [tmp_path])
    assert "ESpeech" in a and "|" not in a and "**" not in a and "decided.md" not in a and "`" not in a
    assert "на слух" in a
