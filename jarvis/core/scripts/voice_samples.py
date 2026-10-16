"""Образцы голосов для JARVIS: послушать и выбрать. Всё бесплатно и локально.

Запуск на ПК владельца (папка C:\\jarvis):

    uv run python core/scripts/voice_samples.py                 # все образцы
    uv run python core/scripts/voice_samples.py --only piper     # только лёгкие голоса Piper (без видеокарты)

Что получится в ``data/voices/samples/``:

1. Piper (sherpa-onnx, процессор): Денис, Дмитрий — свободная лицензия CC0; Ирина — лицензия не указана;
   Руслан — CC BY-NC-SA (только некоммерческое использование).
2. Qwen3-TTS VoiceDesign 1.7B (видеокарта, Apache-2.0): голос по описанию словами — четыре варианта «Джарвиса».
3. Копия голоса владельца — Qwen3-TTS Base 1.7B: если есть ``data/voices/my-voice.wav`` (20–30 секунд чистой речи)
   и ``data/voices/my-voice.txt`` (что именно сказано на записи).

Модели: Piper — с GitHub (k2-fsa/sherpa-onnx, релиз tts-models); Qwen3-TTS — с Hugging Face
(Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign и -Base). Пакеты: ``sherpa-onnx soundfile`` и ``qwen-tts torch``.

Правило (brain/10-rules/always-ask.md): копия голоса владельца — только для разговоров с самим владельцем.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "voices" / "samples"
MODELS = ROOT / "data" / "voices" / "models"

TEXT = ("Доброе утро. Вот что я понял за ночь. Планировка квартиры на восемьдесят пять квадратов готова "
        "и проверена до миллиметра. Принтер Бамбу закончит печать в два часа двадцать минут. "
        "По одной заявке нужно ваше решение. Свет за сутки обошёлся в два сомони.")

PIPER = {  # имя файла → голос
    "piper-1-denis": "denis",
    "piper-2-dmitri": "dmitri",
    "piper-3-irina": "irina",
    "piper-4-ruslan": "ruslan",
}
PIPER_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-ru_RU-{v}-medium.tar.bz2"

# Описания для VoiceDesign. Модель лучше понимает описания на английском — владельцу показываем русские подписи.
DESIGN = {
    "qwen-1-dvoreckij": ("Дворецкий: спокойный низкий голос, сдержанно и вежливо",
                         "A calm, deep male baritone, about 45 years old. Polite, restrained British-butler manner, "
                         "measured pace, warm but formal, clear diction."),
    "qwen-2-inzhener": ("Инженер: уверенно, коротко, по делу",
                        "A confident male voice, around 35. Precise and businesslike, slightly fast, "
                        "no emotion exaggeration, like an engineer giving a status report."),
    "qwen-3-myagkij": ("Мягкий: тёплый голос, неторопливо",
                       "A warm, soft male voice, around 40, unhurried and reassuring, gentle smile in the voice."),
    "qwen-4-assistentka": ("Ассистентка: спокойный женский голос",
                           "A calm, clear female voice, around 30, professional assistant tone, friendly and composed."),
}


def _write(path: Path, samples, sr: int) -> None:
    import soundfile as sf
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path.with_suffix(".wav")), samples, sr)
    print(f"  готово: {path.with_suffix('.wav').name}")


def piper() -> None:
    import numpy as np
    import sherpa_onnx
    print("Piper — лёгкие голоса на процессоре")
    for name, v in PIPER.items():
        d = MODELS / f"vits-piper-ru_RU-{v}-medium"
        if not d.exists():
            MODELS.mkdir(parents=True, exist_ok=True)
            arch = MODELS / f"{v}.tar.bz2"
            print(f"  скачиваю голос {v}…")
            urllib.request.urlretrieve(PIPER_URL.format(v=v), arch)
            with tarfile.open(arch) as t:
                t.extractall(MODELS)
            arch.unlink()
        cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=str(d / f"ru_RU-{v}-medium.onnx"),
                                                       tokens=str(d / "tokens.txt"), data_dir=str(d / "espeak-ng-data")),
            num_threads=4))
        audio = sherpa_onnx.OfflineTts(cfg).generate(TEXT, sid=0, speed=1.0)
        _write(OUT / name, np.array(audio.samples, dtype="float32"), audio.sample_rate)


def _russian(model) -> str:
    langs = [str(x) for x in (model.get_supported_languages() or [])]
    for lang in langs:
        if lang.lower() in {"russian", "ru"}:
            return lang
    raise SystemExit(f"Модель не знает русского. Поддерживает: {', '.join(langs)}")


def qwen(design: bool = True, clone: bool = True) -> None:
    import torch
    from qwen_tts import Qwen3TTSModel
    kw = dict(device_map="cuda:0", dtype=torch.bfloat16) if torch.cuda.is_available() else dict(device_map="cpu")
    if design:
        print("Qwen3-TTS — голос по описанию (видеокарта)")
        m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", **kw)
        lang = _russian(m)
        for name, (label, instruct) in DESIGN.items():
            wavs, sr = m.generate_voice_design(text=TEXT, instruct=instruct, language=lang)
            _write(OUT / name, wavs[0], sr)
            (OUT / f"{name}.txt").write_text(label + "\n", encoding="utf-8")
        del m
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    ref = ROOT / "data" / "voices" / "my-voice.wav"
    ref_text = ref.with_suffix(".txt")
    if clone and ref.exists() and ref_text.exists():
        print("Qwen3-TTS — копия вашего голоса")
        m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-Base", **kw)
        wavs, sr = m.generate_voice_clone(text=TEXT, language=_russian(m), ref_audio=str(ref),
                                          ref_text=ref_text.read_text(encoding="utf-8").strip())
        _write(OUT / "qwen-5-vash-golos", wavs[0], sr)
    elif clone:
        print("Копию вашего голоса пропускаю: нет data/voices/my-voice.wav и my-voice.txt")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Образцы голосов JARVIS")
    ap.add_argument("--only", choices=["piper", "design", "clone"], help="сделать только одну группу")
    a = ap.parse_args(argv)
    if a.only in (None, "piper"):
        piper()
    if a.only in (None, "design", "clone"):
        qwen(design=a.only in (None, "design"), clone=a.only in (None, "clone"))
    print(f"Образцы лежат в {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
