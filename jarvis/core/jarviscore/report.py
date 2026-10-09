"""Единый формат отчёта JARVIS (ТЗ §13): реальные результаты, а не «работа продолжается»."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Report:
    project: str
    done: list[str] = field(default_factory=list)          # что реально сделано (проверяемо)
    decisions: list[str] = field(default_factory=list)     # что требует вашего решения
    next_step: str = ""                                    # следующий этап
    files: list[str] = field(default_factory=list)         # файлы, ссылки, скриншоты
    checks: list[str] = field(default_factory=list)        # как проверено (тесты, скриншот, ручная проверка)
    limits: list[str] = field(default_factory=list)        # известные ограничения

    def render(self) -> str:
        lines = [f"📌 {self.project}"]
        lines.append("✅ Сделано: " + ("; ".join(self.done) if self.done else "пока ничего проверяемого"))
        if self.checks:
            lines.append("🔎 Проверено: " + "; ".join(self.checks))
        lines.append("❓ Нужно решить: " + ("; ".join(self.decisions) if self.decisions else "ничего"))
        lines.append("➡️ Следующий шаг: " + (self.next_step or "—"))
        if self.limits:
            lines.append("⚠️ Ограничения: " + "; ".join(self.limits))
        lines.append("📎 Файлы: " + (", ".join(self.files) if self.files else "нет"))
        return "\n".join(lines)
