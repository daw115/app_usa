from __future__ import annotations

from dataclasses import dataclass

from backend.models import Settings


@dataclass
class CostBreakdown:
    auction_usd: float
    agent_fee_usd: float
    transport_usd: float
    repair_usd_mid: float
    usd_subtotal: float
    usd_pln_rate: float
    pln_before_taxes: float
    customs_pln: float
    excise_pln: float
    vat_pln: float
    margin_pln: float
    total_pln: float


def midpoint(low: float | None, high: float | None, safety_pct: float) -> float:
    if low is None or high is None:
        return 0.0
    mid = (low + high) / 2.0
    return mid * (1.0 + safety_pct)


def calculate(
    auction_usd: float,
    repair_low_usd: float | None,
    repair_high_usd: float | None,
    settings: Settings,
) -> CostBreakdown:
    repair_usd = midpoint(repair_low_usd, repair_high_usd, settings.repair_safety_pct)

    usd_subtotal = auction_usd + settings.agent_fee_usd + settings.transport_usd
    pln_before_taxes = usd_subtotal * settings.usd_pln_rate

    customs_base_pln = auction_usd * settings.usd_pln_rate
    customs_pln = customs_base_pln * settings.customs_pct
    excise_pln = (customs_base_pln + customs_pln) * settings.excise_pct
    vat_base_pln = customs_base_pln + customs_pln + excise_pln
    vat_pln = vat_base_pln * settings.vat_pct

    repair_pln = repair_usd * settings.usd_pln_rate

    total = (
        pln_before_taxes
        + customs_pln
        + excise_pln
        + vat_pln
        + repair_pln
        + settings.margin_pln
    )

    return CostBreakdown(
        auction_usd=auction_usd,
        agent_fee_usd=settings.agent_fee_usd,
        transport_usd=settings.transport_usd,
        repair_usd_mid=repair_usd,
        usd_subtotal=usd_subtotal,
        usd_pln_rate=settings.usd_pln_rate,
        pln_before_taxes=pln_before_taxes,
        customs_pln=customs_pln,
        excise_pln=excise_pln,
        vat_pln=vat_pln,
        margin_pln=settings.margin_pln,
        total_pln=round(total, 2),
    )


async def fetch_nbp_usd_rate() -> float | None:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("https://api.nbp.pl/api/exchangerates/rates/a/usd/?format=json")
            r.raise_for_status()
            return float(r.json()["rates"][0]["mid"])
    except Exception:
        return None
