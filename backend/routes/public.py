from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session

from backend.db import engine
from backend.models import DamageTolerance, Inquiry, InquiryStatus, Listing

router = APIRouter()
templates = Jinja2Templates(directory="frontend")
limiter = Limiter(key_func=get_remote_address)


@router.get("/form", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse("form.html", {"request": request, "submitted": False})


@router.get("/track/{inquiry_id}/{token}", response_class=HTMLResponse)
async def track_inquiry(request: Request, inquiry_id: int, token: str):
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
    background: BackgroundTasks,
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
    def to_int(v: str):
        try:
            return int(v) if v.strip() else None
        except ValueError:
            return None

    inquiry = Inquiry(
        client_name=client_name.strip(),
        client_email=client_email.strip(),
        client_phone=client_phone.strip(),
        make=make.strip(),
        model=model.strip(),
        year_from=to_int(year_from),
        year_to=to_int(year_to),
        budget_pln=to_int(budget_pln),
        mileage_max=to_int(mileage_max),
        body_type=body_type.strip(),
        fuel=fuel.strip(),
        transmission=transmission.strip(),
        damage_tolerance=DamageTolerance(damage_tolerance),
        extra_notes=extra_notes.strip(),
        status=InquiryStatus.new,
    )
    with Session(engine) as s:
        s.add(inquiry)
        s.commit()
        s.refresh(inquiry)
        inquiry_id = inquiry.id

    from backend.services.telegram_bot import notify_new_inquiry
    background.add_task(notify_new_inquiry, inquiry_id)

    return templates.TemplateResponse("form.html", {"request": request, "submitted": True})
