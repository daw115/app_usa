from backend.models import Settings
from backend.services.pricing import calculate


def test_calculate_zero_repair():
    s = Settings(
        id=1, transport_usd=1500, agent_fee_usd=600,
        customs_pct=0.10, excise_pct=0.186, vat_pct=0.23,
        margin_pln=5000, repair_safety_pct=0.25, usd_pln_rate=4.0,
    )
    b = calculate(auction_usd=10000, repair_low_usd=None, repair_high_usd=None, settings=s)
    assert b.total_pln > 10000 * 4.0
    assert b.margin_pln == 5000
    assert b.repair_usd_mid == 0


def test_calculate_with_repair_applies_safety_margin():
    s = Settings(id=1, repair_safety_pct=0.20, usd_pln_rate=4.0)
    b = calculate(auction_usd=15000, repair_low_usd=2000, repair_high_usd=3000, settings=s)
    assert b.repair_usd_mid == 2500 * 1.2
    assert b.total_pln > 15000 * 4.0


def test_calculate_higher_auction_higher_total():
    s = Settings(id=1)
    low = calculate(10000, 0, 0, s).total_pln
    high = calculate(20000, 0, 0, s).total_pln
    assert high > low
