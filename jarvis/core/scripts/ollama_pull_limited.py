"""Скачать модель Ollama с ограничением скорости (правило владельца: качать не больше 30 из 50 Мбит/с).

У ``ollama pull`` нет ограничения скорости, поэтому файлы модели качаем сами через curl
(``--limit-rate``, докачка с места обрыва ``-C -``), проверяем контрольную сумму и кладём
в папку моделей Ollama (``OLLAMA_MODELS``) так же, как это делает ``ollama pull``.

Запуск:  python ollama_pull_limited.py qwen3.5:27b gemma3:27b  [--rate 3.5M] [--models C:\\Work\\AI]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

REGISTRY = "https://registry.ollama.ai"
ACCEPT = "application/vnd.docker.distribution.manifest.v2+json"


def manifest(name: str, tag: str) -> bytes:
    req = urllib.request.Request(f"{REGISTRY}/v2/library/{name}/manifests/{tag}", headers={"Accept": ACCEPT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_blob(name: str, digest: str, size: int, blobs: Path, rate: str) -> None:
    final = blobs / digest.replace(":", "-")
    if final.exists() and final.stat().st_size == size:
        print(f"  есть: {digest[:19]} ({size / 1e9:.2f} ГБ)", flush=True)
        return
    part = final.with_name(final.name + "-limited")
    print(f"  качаю: {digest[:19]} ({size / 1e9:.2f} ГБ) не быстрее {rate}/с", flush=True)
    for attempt in range(20):   # сеть рвётся — докачиваем с места обрыва
        code = subprocess.run(["curl", "-L", "-f", "-sS", "--limit-rate", rate, "-C", "-", "-o", str(part),
                               f"{REGISTRY}/v2/library/{name}/blobs/{digest}"]).returncode
        if code == 0 and part.stat().st_size == size:
            break
        print(f"  обрыв (код {code}), попытка {attempt + 2}", flush=True)
    else:
        sys.exit(f"не удалось скачать {digest}")
    if "sha256:" + sha256(part) != digest:
        part.unlink()
        sys.exit(f"контрольная сумма не сошлась: {digest} — файл удалён, запустите ещё раз")
    os.replace(part, final)


def pull(model: str, root: Path, rate: str) -> None:
    name, _, tag = model.partition(":")
    tag = tag or "latest"
    raw = manifest(name, tag)
    m = json.loads(raw)
    blobs = root / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    print(f"{model}: {len(m['layers']) + 1} файлов", flush=True)
    for layer in [m["config"], *m["layers"]]:
        fetch_blob(name, layer["digest"], layer["size"], blobs, rate)
    dest = root / "manifests" / "registry.ollama.ai" / "library" / name / tag
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)       # последним: пока файлы не все, Ollama модель не видит
    print(f"{model}: готово", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("models", nargs="+")
    p.add_argument("--rate", default="3.5M", help="потолок скорости для curl: 3.5M ≈ 30 Мбит/с")
    p.add_argument("--models-dir", default=os.environ.get("OLLAMA_MODELS", r"C:\Work\AI"))
    a = p.parse_args()
    for model in a.models:
        pull(model, Path(a.models_dir), a.rate)


if __name__ == "__main__":
    main()
