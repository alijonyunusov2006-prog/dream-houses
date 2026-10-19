import sys
import types

from jarviscore import stt


class FakeModel:
    def __init__(self, name, device, compute_type):
        self.device = device

    def transcribe(self, audio, **kw):
        if self.device == "cuda":
            raise RuntimeError("Library cublas64_12.dll is not found")
        return iter([types.SimpleNamespace(text=" привет "), types.SimpleNamespace(text="мир")]), None


def test_gpu_failure_during_work_falls_back_to_cpu(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(stt, "decode", lambda path: [0.0])
    tr = stt.Transcriber()
    assert tr.transcribe("voice.ogg") == "привет мир"
    assert tr.device == "cpu"
    assert tr.transcribe("voice.ogg") == "привет мир"      # дальше сразу процессор, без новой попытки
