"""План месяца: от целевой прибыли назад к заказам, встречам, заявкам и рекламе.

Все входные цифры — из DH OS за прошлые месяцы (средний чек, маржа, конверсии) и из рекламного
кабинета (цена заявки). Модуль только считает; данные не выдумывает и не подставляет «типичные».
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Funnel:
    avg_check: float            # средний договор, сомони
    margin: float               # доля прибыли с договора после прямых расходов, 0..1
    lead_to_meeting: float      # заявка → встреча (замер, консультация), 0..1
    meeting_to_deal: float      # встреча → договор, 0..1
    cost_per_lead: float = 0.0  # цена заявки из рекламы, сомони (0 — без рекламы)
    fixed_costs: float = 0.0    # постоянные расходы месяца: аренда, зарплаты, сервисы, сомони

    def __post_init__(self) -> None:
        for name in ("margin", "lead_to_meeting", "meeting_to_deal"):
            v = getattr(self, name)
            if not 0 < v <= 1:
                raise ValueError(f"{name} должно быть от 0 до 1, а не {v}")
        if self.avg_check <= 0:
            raise ValueError("средний чек должен быть больше нуля")


@dataclass(frozen=True)
class MonthPlan:
    deals: int
    meetings: int
    leads: int
    revenue: float
    gross_profit: float
    ad_budget: float
    net_profit: float


def plan_for_profit(target_net_profit: float, f: Funnel) -> MonthPlan:
    """Сколько нужно договоров, встреч и заявок, чтобы чистая прибыль была не ниже цели."""
    per_deal = f.avg_check * f.margin - f.cost_per_lead / (f.lead_to_meeting * f.meeting_to_deal)
    if per_deal <= 0:
        raise ValueError("каждый договор убыточен: реклама на один договор дороже прибыли с него")
    deals = max(0, math.ceil((target_net_profit + f.fixed_costs) / per_deal - 1e-9))
    return plan_for_deals(deals, f)


def plan_for_deals(deals: int, f: Funnel) -> MonthPlan:
    meetings = math.ceil(deals / f.meeting_to_deal - 1e-9)
    leads = math.ceil(meetings / f.lead_to_meeting - 1e-9)
    revenue = deals * f.avg_check
    gross = revenue * f.margin
    ads = leads * f.cost_per_lead
    return MonthPlan(deals=deals, meetings=meetings, leads=leads, revenue=round(revenue, 2),
                     gross_profit=round(gross, 2), ad_budget=round(ads, 2),
                     net_profit=round(gross - ads - f.fixed_costs, 2))


def plan_vs_fact(plan: float, fact: float, day: int, days_in_month: int) -> dict:
    """Отставание с учётом прошедших дней: идём ли к плану к концу месяца."""
    expected = plan * day / days_in_month
    forecast = fact / day * days_in_month if day else 0.0
    return {
        "expected_by_now": round(expected, 2),
        "fact": fact,
        "gap": round(fact - expected, 2),
        "forecast": round(forecast, 2),
        "on_track": forecast >= plan,
    }
