import pytest

from jarviscore.bizplan import Funnel, plan_for_deals, plan_for_profit, plan_vs_fact

F = Funnel(avg_check=10_000, margin=0.5, lead_to_meeting=0.5, meeting_to_deal=0.4,
           cost_per_lead=50, fixed_costs=20_000)


def test_funnel_back_calculation():
    p = plan_for_deals(10, F)
    assert (p.deals, p.meetings, p.leads) == (10, 25, 50)
    assert p.revenue == 100_000 and p.ad_budget == 2_500
    assert p.net_profit == 100_000 * 0.5 - 2_500 - 20_000


def test_plan_reaches_target_profit():
    p = plan_for_profit(30_000, F)
    assert p.net_profit >= 30_000
    assert plan_for_deals(p.deals - 1, F).net_profit < 30_000   # минимально достаточно


def test_unprofitable_ads_are_reported():
    bad = Funnel(avg_check=1_000, margin=0.1, lead_to_meeting=0.1, meeting_to_deal=0.1, cost_per_lead=50)
    with pytest.raises(ValueError):
        plan_for_profit(1_000, bad)


def test_rates_are_validated():
    with pytest.raises(ValueError):
        Funnel(avg_check=1, margin=1.5, lead_to_meeting=0.5, meeting_to_deal=0.5)


def test_plan_vs_fact():
    r = plan_vs_fact(plan=20, fact=8, day=15, days_in_month=30)
    assert r["expected_by_now"] == 10 and r["gap"] == -2 and r["forecast"] == 16 and not r["on_track"]
