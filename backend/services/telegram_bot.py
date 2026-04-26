from __future__ import annotations

import asyncio
import logging

import httpx
from sqlmodel import Session, select

from backend.config import config
from backend.db import engine
from backend.models import Inquiry, Report

log = logging.getLogger(__name__)


async def _send(text: str, reply_markup: dict | None = None) -> None:
    if not config.telegram_bot_token or not config.telegram_chat_id:
        log.info("Telegram disabled (no token/chat id): %s", text[:120])
        return
    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code >= 400:
                log.error("telegram send failed: %s %s", r.status_code, r.text)
    except Exception as e:
        log.error("telegram send error: %s", e)


def _dashboard_url(path: str) -> str:
    base = (config.public_form_base_url or "http://localhost:8000").rstrip("/")
    return f"{base}{path}"


async def notify_new_inquiry(inquiry_id: int) -> None:
    with Session(engine) as s:
        inq = s.get(Inquiry, inquiry_id)
        if not inq:
            return
        text = (
            f"🚗 <b>Nowe zapytanie #{inq.id}</b>\n"
            f"<b>{inq.client_name}</b> — {inq.client_phone or inq.client_email}\n"
            f"{inq.make} {inq.model}, {inq.year_from or '?'}-{inq.year_to or '?'}\n"
            f"Budżet: {inq.budget_pln or '?'} PLN · Szkoda: {inq.damage_tolerance.value}\n"
            f"Uwagi: {(inq.extra_notes or '—')[:200]}"
        )
    markup = {"inline_keyboard": [[
        {"text": "🔍 Otwórz zapytanie", "url": _dashboard_url(f"/inquiry/{inquiry_id}")},
    ]]}
    await _send(text, markup)


async def notify_report_ready(report_id: int) -> None:
    with Session(engine) as s:
        rep = s.get(Report, report_id)
        if not rep:
            return
        inq = s.get(Inquiry, rep.inquiry_id)
        name = inq.client_name if inq else "?"
        text = (
            f"📝 <b>Raport gotowy</b> dla {name}\n"
            f"Zapytanie #{rep.inquiry_id}, raport #{rep.id}"
        )
    markup = {"inline_keyboard": [[
        {"text": "👁 Zobacz raport", "url": _dashboard_url(f"/report/{report_id}/edit")},
    ]]}
    await _send(text, markup)


async def notify_error(inquiry_id: int, message: str) -> None:
    text = f"⚠️ Błąd przy zapytaniu #{inquiry_id}: {message[:300]}"
    await _send(text)


def notify_new_inquiry_sync(inquiry_id: int) -> None:
    try:
        asyncio.run(notify_new_inquiry(inquiry_id))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(notify_new_inquiry(inquiry_id))
        finally:
            loop.close()
