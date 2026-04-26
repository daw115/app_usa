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


async def send_document(file_path: str, caption: str = "") -> bool:
    """Send a file as a Telegram document. Returns True on success.

    Telegram bot API limit: 50MB per file. For larger backups switch to
    external storage.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        log.info("Telegram disabled — skipping send_document(%s)", file_path)
        return False

    import os
    if not os.path.exists(file_path):
        log.error("send_document: file not found %s", file_path)
        return False

    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > 49:
        log.error("send_document: file too large (%.1fMB > 50MB) %s", size_mb, file_path)
        return False

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendDocument"
    try:
        with open(file_path, "rb") as fp:
            files = {"document": (os.path.basename(file_path), fp)}
            data = {"chat_id": config.telegram_chat_id, "caption": caption[:1024]}
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, data=data, files=files)
                if r.status_code >= 400:
                    log.error("telegram send_document failed: %s %s", r.status_code, r.text[:300])
                    return False
        log.info("Telegram document sent: %s (%.1fMB)", file_path, size_mb)
        return True
    except Exception as e:
        log.error("telegram send_document error: %s", e)
        return False


def notify_new_inquiry_sync(inquiry_id: int) -> None:
    try:
        asyncio.run(notify_new_inquiry(inquiry_id))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(notify_new_inquiry(inquiry_id))
        finally:
            loop.close()
