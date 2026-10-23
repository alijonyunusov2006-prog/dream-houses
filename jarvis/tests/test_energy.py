import pytest

from jarviscore.energy import TARIFF_BUSINESS, TARIFF_POPULATION, Profile, estimate_month, integrate_kwh, report_line


def test_idle_month_24_7():
    e = estimate_month(Profile(idle=24), TARIFF_POPULATION)
    assert e.kwh_pc == pytest.approx(79.2)                     # 110 Вт × 720 ч
    assert e.somoni == pytest.approx(32.77, abs=0.01)


def test_business_tariff_is_higher():
    p = Profile(idle=12, work=12)
    assert estimate_month(p, TARIFF_BUSINESS).somoni > estimate_month(p, TARIFF_POPULATION).somoni * 2


def test_printers_counted_separately():
    e = estimate_month(Profile(p1s=8, k1=8))
    assert e.kwh_pc == 0 and e.kwh_printers == pytest.approx(64.8)


def test_more_than_24_hours_is_an_error():
    with pytest.raises(ValueError):
        estimate_month(Profile(idle=20, render=6))


def test_integrate_skips_gaps():
    # 1 час по 500 Вт = 0,5 кВт·ч, потом ПК выключен 3 часа — не считаем
    samples = [(i * 60.0, 500.0) for i in range(61)] + [(4 * 3600.0, 500.0), (4 * 3600.0 + 60, 500.0)]
    assert integrate_kwh(samples) == pytest.approx(0.5 + 500 * 60 / 3600 / 1000, abs=1e-3)


def test_report_line_format():
    assert report_line(3.1) == "⚡ Свет за сутки: 3,1 кВт·ч ≈ 1,28 сомони"
