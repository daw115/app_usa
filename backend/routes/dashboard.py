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
async def inquiry_detail(request: Request, inquiry_id: int):
    with Session(engine) as s:
        inquiry = s.get(Inquiry, inquiry_id)
        if not inquiry:
            raise HTTPException(404)
        listings = s.exec(
            select(Listing).where(Listing.inquiry_id == inquiry_id).order_by(
                Listing.recommended_rank.is_(None), Listing.recommended_rank
            )
        ).all()
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
    from backend.services.gmail import create_draft
    with Session(engine) as s:
        report = s.get(Report, report_id)
        if not report:
            raise HTTPException(404)
        inquiry = s.get(Inquiry, report.inquiry_id)
    try:
        draft_id = create_draft(inquiry.client_email, report.subject, report.html_body)
    except Exception as e:
        log.exception("gmail draft failed")
        raise HTTPException(500, f"Gmail draft failed: {e}")
    with Session(engine) as s:
        report = s.get(Report, report_id)
        report.gmail_draft_id = draft_id
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
