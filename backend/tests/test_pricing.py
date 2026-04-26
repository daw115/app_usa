import pytest
from backend.services.pricing import calculate, midpoint
from backend.models import Settings


def test_midpoint_calculation():
    result = midpoint(1000.0, 2000.0, 0.2)
    assert result == 1800.0  # (1000 + 2000) / 2 * 1.2


def test_midpoint_with_none():
    result = midpoint(None, 2000.0, 0.2)
    assert result == 0.0

    result = midpoint(1000.0, None, 0.2)
    assert result == 0.0


def test_calculate_cost_breakdown():
    settings = Settings(
        id=1,
        usd_pln_rate=4.0,
        agent_fee_usd=300,
        transport_usd=1000,
        customs_pct=0.10,
        excise_pct=0.03,
        vat_pct=0.23,
        margin_pln=5000,
        repair_safety_pct=0.20,
    )

    breakdown = calculate(
        auction_usd=10000.0,
        repair_low_usd=500.0,
        repair_high_usd=1000.0,
        settings=settings,
    )

    assert breakdown.auction_usd == 10000.0
    assert breakdown.agent_fee_usd == 300.0
    assert breakdown.transport_usd == 1000.0
    assert breakdown.repair_usd_mid == 900.0  # (500 + 1000) / 2 * 1.2
    assert breakdown.usd_pln_rate == 4.0
    assert breakdown.margin_pln == 5000.0
    assert breakdown.total_pln > 0


def test_calculate_with_no_repair():
    settings = Settings(
        id=1,
        usd_pln_rate=4.0,
        agent_fee_usd=300,
        transport_usd=1000,
        customs_pct=0.10,
        excise_pct=0.03,
        vat_pct=0.23,
        margin_pln=5000,
        repair_safety_pct=0.20,
    )

    breakdown = calculate(
        auction_usd=10000.0,
        repair_low_usd=None,
        repair_high_usd=None,
        settings=settings,
    )

    assert breakdown.repair_usd_mid == 0.0
    assert breakdown.total_pln > 0
