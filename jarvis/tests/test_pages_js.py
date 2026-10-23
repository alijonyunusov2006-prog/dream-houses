"""Код страниц (окно JARVIS, 3D-офис) без синтаксических ошибок.

Урок 2026-10-21: комментарий «//» посреди строки съел конец кода — окно JARVIS молча перестало работать,
а проверки данных этого не видели. Теперь каждый блок <script> проверяет node --check.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "core" / "jarviscore" / "web" / "index.html", ROOT / "docs" / "office3d" / "index.html"]
NODE = shutil.which("node")


@pytest.mark.skipif(not NODE, reason="node не установлен")
@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.parent.name)
def test_inline_scripts_parse(page, tmp_path):
    html = page.read_text(encoding="utf-8")
    blocks = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", html, re.S)
    checked = 0
    for i, (attrs, code) in enumerate(blocks):
        if "importmap" in attrs:
            continue
        f = tmp_path / (f"b{i}.mjs" if "module" in attrs else f"b{i}.js")
        f.write_text(code, encoding="utf-8")
        r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, f"{page.parent.name}, блок {i}: {r.stderr[:500]}"
        checked += 1
    assert checked >= 1


@pytest.mark.skipif(not NODE, reason="node не установлен")
def test_window_scripts_parse():
    for f in (ROOT / "core" / "jarviscore" / "web").glob("*.js"):
        r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, f"{f.name}: {r.stderr[:500]}"
