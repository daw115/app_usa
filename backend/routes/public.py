from __future__ import annotations

import json
import re

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from backend.db import engine
from backend.models import DamageTolerance, Inquiry, InquiryStatus, Listing

router = APIRouter()
templates = Jinja2Templates(directory="frontend")
limiter = Limiter(key_func=get_remote_address)

# Email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validate_email(email: str) -> bool:
    """Validate email format"""
    return bool(EMAIL_REGEX.match(email)) and len(email) <= 254

def sanitize_string(s: str, max_length: int = 500) -> str:
    """Sanitize user input - remove potential SQL injection patterns"""
    if not s:
        return ""
    # Strip whitespace and limit length
    s = s.strip()[:max_length]
    # Remove null bytes and control characters
    s = ''.join(char for char in s if ord(char) >= 32 or char in '\n\r\t')
    return s


@router.get("/form", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse("form.html", {"request": request, "submitted": False})


@router.get("/track/{inquiry_id}/{token}", response_class=HTMLResponse)
async def track_inquiry(request: Request, inquiry_id: int, token: str):
    # Sanitize token to prevent injection
    token = sanitize_string(token, 100)

    with Session(engine) as s:
        inquiry = s.get(Inquiry, inquiry_id)
        if not inquiry or inquiry.tracking_token != token:
            raise HTTPException(404, "Zapytanie nie znalezione")

        listings = s.exec(
            select(Listing)
            .where(Listing.inquiry_id == inquiry_id)
            .where(Listing.excluded == False)
        ).all()

        listings_data = []
        for l in listings:
            photos = json.loads(l.photos_json or "[]")
            listings_data.append({
                "year": l.year,
                "make": l.make,
                "model": l.model,
                "source": l.source,
                "photos": photos[:1],
            })

    return templates.TemplateResponse("track.html", {
        "request": request,
        "inquiry": inquiry,
        "listings": listings_data,
        "listings_count": len(listings_data),
    })


@router.post("/inquiry", response_class=HTMLResponse)
@limiter.limit("10/hour")
async def submit_inquiry(
    request: Request,
    client_name: str = Form(...),
    client_email: str = Form(...),
    client_phone: str = Form(""),
    make: str = Form(""),
    model: str = Form(""),
    year_from: str = Form(""),
    year_to: str = Form(""),
    budget_pln: str = Form(""),
    mileage_max: str = Form(""),
    body_type: str = Form(""),
    fuel: str = Form(""),
    transmission: str = Form(""),
    damage_tolerance: str = Form("light"),
    extra_notes: str = Form(""),
):
    # Validate and sanitize inputs
    client_name = sanitize_string(client_name, 200)
    client_email = sanitize_string(client_email, 254)
    client_phone = sanitize_string(client_phone, 50)

    # Validate required fields
    if not client_name or len(client_name) < 2:
        raise HTTPException(400, "Imię i nazwisko jest wymagane (min. 2 znaki)")

    if not client_email or not validate_email(client_email):
        raise HTTPException(400, "Nieprawidłowy adres email")

    # Validate damage_tolerance enum
    try:
        damage_tolerance_enum = DamageTolerance(damage_tolerance)
    except ValueError:
        raise HTTPException(400, "Nieprawidłowa wartość tolerancji uszkodzeń")

    def to_int(v: str):
        try:
            return int(v) if v.strip() else None
        except ValueError:
            return None

    inquiry = Inquiry(
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        make=sanitize_string(make, 100),
        model=sanitize_string(model, 100),
        year_from=to_int(year_from),
        year_to=to_int(year_to),
        budget_pln=to_int(budget_pln),
        mileage_max=to_int(mileage_max),
        body_type=sanitize_string(body_type, 50),
        fuel=sanitize_string(fuel, 50),
        transmission=sanitize_string(transmission, 50),
        damage_tolerance=damage_tolerance_enum,
        extra_notes=sanitize_string(extra_notes, 1000),
        status=InquiryStatus.new,
    )
    with Session(engine) as s:
        s.add(inquiry)
        s.commit()
        s.refresh(inquiry)
        inquiry_id = inquiry.id
        tracking_token = inquiry.tracking_token

    from backend.services.gmail import send_tracking_email
    from backend.services.telegram_bot import notify_new_inquiry
    from backend.tasks import run_search_pipeline
    import asyncio

    # Telegram notification to Janek
    asyncio.create_task(notify_new_inquiry(inquiry_id))
    # Tracking email to client (sync smtplib — wrap in to_thread so it doesn't
    # block the event loop)
    asyncio.create_task(asyncio.to_thread(
        send_tracking_email, client_name, client_email, inquiry_id, tracking_token,
    ))
    # Auto-trigger search pipeline. Cron (auto_search_job, every 30min) is a
    # safety net for cases where this task crashes before persisting status.
    asyncio.create_task(run_search_pipeline(inquiry_id))

    return templates.TemplateResponse("form.html", {"request": request, "submitted": True})
