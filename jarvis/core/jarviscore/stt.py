"""Голос → текст на ПК: faster-whisper (бесплатно, офлайн; решение владельца — только локально).

Видеокарта (RTX 3090) — модель ``large-v3``. Если видеокарта недоступна (занята рендером,
нет библиотек CUDA), — процессор и модель полегче: голосовое всё равно расшифруется, только медленнее.
Модель грузится один раз при первом голосовом и дальше держится в памяти.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def _add_cuda_dlls() -> None:
    """Библиотеки CUDA из пакетов nvidia-* (pip) — подключить к поиску DLL на Windows."""
    if sys.platform != "win32":
        return
    for base in map(Path, sys.path):
        for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin"):
            d = base / sub
            if d.is_dir():
                os.add_dll_directory(str(d))
                os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


class Transcriber:
    def __init__(self, model: str = "large-v3", language: str = "ru", cpu_model: str = "medium"):
        self.model_name, self.language, self.cpu_model = model, language, cpu_model
        self._model = None
        self.device = ""

    def _load(self, device: str):
        from faster_whisper import WhisperModel  # тяжёлый импорт — только когда пришло голосовое

        if device == "cuda":
            _add_cuda_dlls()
            self._model = WhisperModel(self.model_name, device="cuda", compute_type="float16")
        else:
            self._model = WhisperModel(self.cpu_model, device="cpu", compute_type="int8")
        self.device = device
        return self._model

    def _run(self, audio) -> str:
        segments, _info = self._model.transcribe(audio, language=self.language, vad_filter=True, beam_size=5)
        return " ".join(s.text.strip() for s in segments).strip()

    def transcribe(self, path: Path | str) -> str:
        audio = decode(path)
        if self._model is None or self.device == "cuda":
            try:
                if self._model is None:
                    self._load("cuda")
                return self._run(audio)
            except Exception as e:  # нет CUDA или видеокарта занята — работаем на процессоре
                log.warning("видеокарта недоступна для распознавания (%s), перехожу на процессор", e)
                self._load("cpu")
        return self._run(audio)


def decode(audio: Path | str):
    """Голосовое (ogg/opus из Telegram и др.) → моно 16 кГц через ffmpeg.

    Свой декодер faster-whisper (PyAV) ломается при несовпадении версий; ffmpeg на ПК есть всегда.
    """
    import numpy as np

    out = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(audio), "-f", "s16le",
                          "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True, timeout=300).stdout
    return np.frombuffer(out, np.int16).astype(np.float32) / 32768.0
