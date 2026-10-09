"""Свет: сколько электричества тратит ПК (и принтеры) и сколько это стоит.

Два способа:

* ``estimate_month(profile, tariff)`` — оценка по режимам (сколько часов ПК ждёт, сколько работает
  локальная модель, рендер, печать). Нужна до установки и для сравнения сценариев.
* ``integrate_kwh(samples)`` — по реальным замерам мощности (Вт) с отметками времени. Замеры пишет
  агент ``sysadmin``: видеокарта — ``nvidia-smi --query-gpu=power.draw``, процессор — датчик пакета
  через LibreHardwareMonitor, остальное — постоянная добавка из ``[energy] base_watts``. Самый точный
  способ — розетка со счётчиком (покупка только с согласия владельца).

Тарифы Таджикистана с 1 февраля 2026 года (постановление Правительства № 709 от 29.12.2025):
население — 41,37 дирама за кВт·ч, промышленные и непромышленные потребители — 94,65 дирама.
"""

from __future__ import annotations

from dataclasses import dataclass

TARIFF_POPULATION = 0.4137      # сомони за кВт·ч
TARIFF_BUSINESS = 0.9465        # сомони за кВт·ч

# Средняя мощность «из розетки» для ПК владельца (i9-13900K, RTX 3090), Вт. Оценка, уточняется замерами.
WATTS = {
    "idle": 110,          # Джарвис ждёт: слушает «Джарвис», очередь, без монитора
    "work": 300,          # обычная работа в 3ds Max / браузере с монитором
    "local_ai": 450,      # локальная модель, распознавание и синтез речи на видеокарте
    "render": 650,        # полный рендер (процессор + видеокарта)
    "p1s": 120,           # Bambu Lab P1S, печать PLA, среднее
    "k1": 150,            # Creality K1, печать PLA, среднее
}


@dataclass(frozen=True)
class Profile:
    """Часы в сутки по режимам. Сумма часов ПК не больше 24; принтеры считаются отдельно."""
    idle: float = 0.0
    work: float = 0.0
    local_ai: float = 0.0
    render: float = 0.0
    p1s: float = 0.0
    k1: float = 0.0
    days: int = 30

    def pc_hours(self) -> float:
        return self.idle + self.work + self.local_ai + self.render


@dataclass(frozen=True)
class Estimate:
    kwh_pc: float
    kwh_printers: float
    tariff: float

    @property
    def kwh(self) -> float:
        return self.kwh_pc + self.kwh_printers

    @property
    def somoni(self) -> float:
        return round(self.kwh * self.tariff, 2)

    @property
    def somoni_pc(self) -> float:
        return round(self.kwh_pc * self.tariff, 2)

    @property
    def somoni_printers(self) -> float:
        return round(self.kwh_printers * self.tariff, 2)


def estimate_month(profile: Profile, tariff: float = TARIFF_POPULATION, watts: dict[str, float] | None = None) -> Estimate:
    if profile.pc_hours() > 24 + 1e-9:
        raise ValueError(f"в сутках 24 часа, а у ПК {profile.pc_hours()}")
    w = {**WATTS, **(watts or {})}
    pc = sum(getattr(profile, k) * w[k] for k in ("idle", "work", "local_ai", "render")) * profile.days / 1000
    pr = sum(getattr(profile, k) * w[k] for k in ("p1s", "k1")) * profile.days / 1000
    return Estimate(kwh_pc=round(pc, 2), kwh_printers=round(pr, 2), tariff=tariff)


def integrate_kwh(samples: list[tuple[float, float]], max_gap_sec: float = 600) -> float:
    """Интеграл мощности по времени. ``samples`` — пары (unix-время, Вт), по возрастанию времени.

    Промежуток длиннее ``max_gap_sec`` (ПК был выключен или спал) не считаем.
    """
    total_wh = 0.0
    for (t0, p0), (t1, p1) in zip(samples, samples[1:]):
        dt = t1 - t0
        if dt <= 0 or dt > max_gap_sec:
            continue
        total_wh += (p0 + p1) / 2 * dt / 3600
    return round(total_wh / 1000, 4)


def report_line(kwh: float, tariff: float = TARIFF_POPULATION, period: str = "за сутки") -> str:
    """Строка для отчёта в Telegram: «⚡ Свет за сутки: 3,1 кВт·ч ≈ 1,28 сомони»."""
    cost = kwh * tariff
    fmt = lambda x: f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")  # noqa: E731
    return f"⚡ Свет {period}: {fmt(kwh)} кВт·ч ≈ {fmt(cost)} сомони"
