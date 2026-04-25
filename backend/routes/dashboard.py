from __future__ import annotations

import asyncio
import json
import logging  # noqa: F401

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from backend.db import engine
from backend.models import Inquiry, InquiryStatus, Listing, Report, ReportStatus, Settings, Source
from backend.tasks import generate_report, run_search_pipeline

log = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="frontend")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, status: str | None = None):
    with Session(engine) as s:
        q = select(Inquiry).order_by(Inquiry.created_at.desc())
        if status:
            q = q.where(Inquiry.status == InquiryStatus(status))
        inquiries = s.exec(q).all()
    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "inquiries": inquiries,
        "status_filter": status,
        "statuses": [s.value for s in InquiryStatus],
    })


@router.get("/inquiry/{inquiry_id}", response_class=HTMLResponse)
async def inquiry_detail(
    request: Request,
    inquiry_id: int,
    source: str | None = None,
    damage_min: int | None = None,
    damage_max: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    sort_by: str = "rank",
):
    with Session(engine) as s:
        inquiry = s.get(Inquiry, inquiry_id)
        if not inquiry:
            raise HTTPException(404)

        # Base query
        q = select(Listing).where(Listing.inquiry_id == inquiry_id)

        # Apply filters
        if source:
            q = q.where(Listing.source == Source(source))
        if damage_min is not None:
            q = q.where(Listing.ai_damage_score >= damage_min)
        if damage_max is not None:
            q = q.where(Listing.ai_damage_score <= damage_max)
        if price_min is not None:
            q = q.where(Listing.total_cost_pln >= price_min)
        if price_max is not None:
            q = q.where(Listing.total_cost_pln <= price_max)

        # Apply sorting
        if sort_by == "price_asc":
            q = q.order_by(Listing.total_cost_pln.asc())
        elif sort_by == "price_desc":
            q = q.order_by(Listing.total_cost_pln.desc())
        elif sort_by == "damage_asc":
            q = q.order_by(Listing.ai_damage_score.asc())
        elif sort_by == "damage_desc":
            q = q.order_by(Listing.ai_damage_score.desc())
        else:  # rank (default)
            q = q.order_by(
                Listing.recommended_rank.is_(None),
                Listing.recommended_rank
            )

        listings = s.exec(q).all()
        reports = s.exec(select(Report).where(Report.inquiry_id == inquiry_id).order_by(Report.created_at.desc())).all()

    listings_with_photos = []
    for l in listings:
        listing_dict = {
            "listing": l,
            "photos_list": json.loads(l.photos_json or "[]")
        }
        listings_with_photos.append(listing_dict)

    return templates.TemplateResponse("dashboard/inquiry_detail.html", {
        "request": request,
        "inquiry": inquiry,
        "listings": listings_with_photos,
        "reports": reports,
        "filters": {
            "source": source,
            "damage_min": damage_min,
            "damage_max": damage_max,
            "price_min": price_min,
            "price_max": price_max,
            "sort_by": sort_by,
        },
        "sources": [s.value for s in Source],
    })


@router.post("/inquiry/{inquiry_id}/search")
async def trigger_search(inquiry_id: int, background: BackgroundTasks):
    background.add_task(_run_async, run_search_pipeline, inquiry_id)
    return RedirectResponse(f"/inquiry/{inquiry_id}", status_code=303)


@router.post("/inquiry/{inquiry_id}/add_manual_url")
async def add_manual_url(
    inquiry_id: int,
    url: str = Form(...),
    source: str = Form("manual"),
    title: str = Form(""),
    year: str = Form(""),
    make: str = Form(""),
    model: str = Form(""),
    mileage: str = Form(""),
    damage_primary: str = Form(""),
    bid_usd: str = Form(""),
    photos: str = Form(""),
):
    def _int(v: str):
        try:
            return int(v.strip()) if v.strip() else None
        except ValueError:
            return None

    def _float(v: str):
        try:
            return float(v.replace(",", ".").strip()) if v.strip() else None
        except ValueError:
            return None

    photo_urls = [p.strip() for p in photos.replace("\r", "").split("\n") if p.strip()]

    with Session(engine) as s:
        inquiry = s.get(Inquiry, inquiry_id)
        if not inquiry:
            raise HTTPException(404)
        listing = Listing(
            inquiry_id=inquiry_id,
            source=Source(source) if source in Source.__members__ else Source.manual,
            source_url=url.strip(),
            title=title.strip() or "(ręczne — do analizy)",
            year=_int(year),
            make=make.strip(),
            model=model.strip(),
            mileage=_int(mileage),
            damage_primary=damage_primary.strip(),
            current_bid_usd=_float(bid_usd),
            photos_json=json.dumps(photo_urls),
        )
        s.add(listing)
        s.commit()
    return RedirectResponse(f"/inquiry/{inquiry_id}", status_code=303)


@router.post("/listing/{listing_id}/analyze")
async def analyze_listing_action(listing_id: int, background: BackgroundTasks):
    background.add_task(_run_async, _analyze_and_price, listing_id)
    with Session(engine) as s:
        l = s.get(Listing, listing_id)
        if not l:
            raise HTTPException(404)
        inq_id = l.inquiry_id
    return RedirectResponse(f"/inquiry/{inq_id}", status_code=303)


@router.post("/listing/{listing_id}/toggle")
async def toggle_listing(listing_id: int):
    with Session(engine) as s:
        l = s.get(Listing, listing_id)
        if not l:
            raise HTTPException(404)
        l.excluded = not l.excluded
        s.add(l)
        s.commit()
        inq_id = l.inquiry_id
    return RedirectResponse(f"/inquiry/{inq_id}", status_code=303)


async def _analyze_and_price(listing_id: int) -> None:
    from backend.services import analyzer
    from backend.tasks import _apply_analysis, _get_settings
    with Session(engine) as s:
        listing = s.get(Listing, listing_id)
        if not listing:
            return
        settings = _get_settings(s)
        photos = json.loads(listing.photos_json or "[]")
        if not photos:
            listing.ai_notes = "Brak URL-i zdjęć — dodaj je w formularzu listingu."
            s.add(listing)
            s.commit()
            return
        listing_data = {
            "title": listing.title, "year": listing.year, "make": listing.make,
            "model": listing.model, "mileage": listing.mileage,
            "damage_primary": listing.damage_primary,
            "damage_secondary": listing.damage_secondary,
            "location": listing.location,
            "current_bid_usd": listing.current_bid_usd,
            "buy_now_usd": listing.buy_now_usd, "vin": listing.vin,
        }
        result = await analyzer.analyze_listing(listing_data, photos)
        _apply_analysis(listing, result, settings)
        s.add(listing)
        s.commit()

        all_listings = s.exec(select(Listing).where(Listing.inquiry_id == listing.inquiry_id)).all()
        analyzed = [l for l in all_listings if l.ai_damage_score is not None]
        inquiry = s.get(Inquiry, listing.inquiry_id)
        if analyzed:
            from backend.tasks import _rank
            _rank(analyzed, inquiry)
            for l in analyzed:
                s.add(l)
            s.commit()


@router.post("/inquiry/{inquiry_id}/generate_report")
async def generate(inquiry_id: int, background: BackgroundTasks):
    background.add_task(_run_async, generate_report, inquiry_id)
    return RedirectResponse(f"/inquiry/{inquiry_id}", status_code=303)


@router.get("/report/{report_id}/edit", response_class=HTMLResponse)
async def report_edit(request: Request, report_id: int):
    with Session(engine) as s:
        report = s.get(Report, report_id)
        if not report:
            raise HTTPException(404)
        inquiry = s.get(Inquiry, report.inquiry_id)
    return templates.TemplateResponse("dashboard/report_editor.html", {
        "request": request, "report": report, "inquiry": inquiry,
    })


@router.post("/report/{report_id}/save")
async def report_save(report_id: int, subject: str = Form(...), html_body: str = Form(...)):
    with Session(engine) as s:
        report = s.get(Report, report_id)
        if not report:
            raise HTTPException(404)
        report.subject = subject
        report.html_body = html_body
        s.add(report)
        s.commit()
    return RedirectResponse(f"/report/{report_id}/edit", status_code=303)


@router.post("/report/{report_id}/draft_to_gmail")
async def report_to_gmail(report_id: int):
    from backend.services.gmail import send_email
    with Session(engine) as s:
        report = s.get(Report, report_id)
        if not report:
            raise HTTPException(404)
        inquiry = s.get(Inquiry, report.inquiry_id)
    try:
        result_id = send_email(inquiry.client_email, report.subject, report.html_body)
    except Exception as e:
        log.exception("email send failed")
        raise HTTPException(500, f"Email send failed: {e}")
    with Session(engine) as s:
        report = s.get(Report, report_id)
        report.gmail_draft_id = result_id
        report.status = ReportStatus.approved
        s.add(report)
        s.commit()
    return RedirectResponse(f"/report/{report_id}/edit", status_code=303)


@router.post("/report/{report_id}/mark_sent")
async def mark_sent(report_id: int):
    from datetime import datetime
    with Session(engine) as s:
        report = s.get(Report, report_id)
        if not report:
            raise HTTPException(404)
        report.status = ReportStatus.sent
        report.sent_at = datetime.utcnow()
        inquiry = s.get(Inquiry, report.inquiry_id)
        inquiry.status = InquiryStatus.sent
        s.add(report)
        s.add(inquiry)
        s.commit()
    return RedirectResponse(f"/inquiry/{report.inquiry_id}", status_code=303)


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, period: str = "30"):
    from datetime import datetime, timedelta
    import csv
    from io import StringIO

    with Session(engine) as s:
        # Calculate date range
        if period == "all":
            date_from = None
            period_label = "all time"
        else:
            days = int(period)
            date_from = datetime.utcnow() - timedelta(days=days)
            period_label = f"{days} days"

        # Base query
        q = select(Inquiry)
        if date_from:
            q = q.where(Inquiry.created_at >= date_from)

        inquiries = s.exec(q).all()

        # Calculate stats
        total = len(inquiries)
        sent = len([i for i in inquiries if i.status == InquiryStatus.sent])
        conversion = round((sent / total * 100) if total > 0 else 0, 1)

        # Average cost and damage
        listings_q = select(Listing)
        if date_from:
            listings_q = listings_q.join(Inquiry).where(Inquiry.created_at >= date_from)

        all_listings = s.exec(listings_q).all()
        costs = [l.total_cost_pln for l in all_listings if l.total_cost_pln]
        damages = [l.ai_damage_score for l in all_listings if l.ai_damage_score]

        avg_cost = sum(costs) / len(costs) if costs else None
        avg_damage = sum(damages) / len(damages) if damages else None

        # Top models
        from collections import Counter
        models = [(i.make, i.model) for i in inquiries if i.make and i.model]
        top_models = [
            {"make": make, "model": model, "count": count}
            for (make, model), count in Counter(models).most_common(5)
        ]

        # Sources breakdown
        sources_count = Counter([l.source.value for l in all_listings])
        total_listings = len(all_listings)
        sources = [
            {
                "source": source,
                "count": count,
                "percentage": round(count / total_listings * 100) if total_listings > 0 else 0
            }
            for source, count in sources_count.most_common()
        ]

        stats = {
            "inquiries_count": total,
            "conversion_rate": conversion,
            "avg_cost_pln": avg_cost,
            "avg_damage_score": avg_damage,
            "top_models": top_models,
            "sources": sources,
        }

    return templates.TemplateResponse("dashboard/analytics.html", {
        "request": request,
        "stats": stats,
        "period": period_label,
        "period_param": period,
    })


@router.get("/analytics/export")
async def analytics_export(period: str = "30"):
    from datetime import datetime, timedelta
    import csv
    from io import StringIO
    from fastapi.responses import StreamingResponse

    with Session(engine) as s:
        # Calculate date range
        if period == "all":
            date_from = None
        else:
            days = int(period)
            date_from = datetime.utcnow() - timedelta(days=days)

        # Get inquiries with listings
        q = select(Inquiry)
        if date_from:
            q = q.where(Inquiry.created_at >= date_from)

        inquiries = s.exec(q).all()

        # Generate CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "inquiry_id", "client_name", "client_email", "created_at", "status",
            "make", "model", "budget_pln", "listings_count", "avg_damage_score", "avg_cost_pln"
        ])

        for inq in inquiries:
            listings = s.exec(select(Listing).where(Listing.inquiry_id == inq.id)).all()
            damages = [l.ai_damage_score for l in listings if l.ai_damage_score]
            costs = [l.total_cost_pln for l in listings if l.total_cost_pln]

            writer.writerow([
                inq.id,
                inq.client_name,
                inq.client_email,
                inq.created_at.strftime("%Y-%m-%d %H:%M"),
                inq.status.value,
                inq.make,
                inq.model,
                inq.budget_pln or "",
                len(listings),
                round(sum(damages) / len(damages), 1) if damages else "",
                round(sum(costs) / len(costs)) if costs else "",
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analytics_{period}days.csv"}
        )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    with Session(engine) as s:
        settings = s.exec(select(Settings).where(Settings.id == 1)).first()
    return templates.TemplateResponse("dashboard/settings.html", {"request": request, "s": settings})


@router.post("/settings")
async def settings_save(
    transport_usd: float = Form(...),
    agent_fee_usd: float = Form(...),
    customs_pct: float = Form(...),
    excise_pct: float = Form(...),
    vat_pct: float = Form(...),
    margin_pln: float = Form(...),
    repair_safety_pct: float = Form(...),
    usd_pln_rate: float = Form(...),
    auto_usd_rate: str = Form("off"),
    auto_search_enabled: str = Form("off"),
):
    with Session(engine) as s:
        settings = s.exec(select(Settings).where(Settings.id == 1)).first()
        settings.transport_usd = transport_usd
        settings.agent_fee_usd = agent_fee_usd
        settings.customs_pct = customs_pct
        settings.excise_pct = excise_pct
        settings.vat_pct = vat_pct
        settings.margin_pln = margin_pln
        settings.repair_safety_pct = repair_safety_pct
        settings.usd_pln_rate = usd_pln_rate
        settings.auto_usd_rate = auto_usd_rate == "on"
        settings.auto_search_enabled = auto_search_enabled == "on"
        s.add(settings)
        s.commit()
    return RedirectResponse("/settings", status_code=303)


def _run_async(coro_fn, *args):
    try:
        asyncio.run(coro_fn(*args))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro_fn(*args))
        finally:
            loop.close()
