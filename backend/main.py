from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from backend.config import config
from backend.db import engine, init_db
from backend.models import Inquiry, InquiryStatus, Settings
from backend.routes import dashboard, public
from backend.tasks import run_search_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# Validate critical env vars
if not config.anthropic_api_key:
    raise RuntimeError("ANTHROPIC_API_KEY is required in .env")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AutoScout US")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

scheduler = AsyncIOScheduler()


async def auto_search_job():
    """Auto-search for new inquiries every 30 minutes"""
    with Session(engine) as s:
        settings = s.exec(select(Settings).where(Settings.id == 1)).first()
        if not settings or not settings.auto_search_enabled:
            return

        # Find new inquiries
        new_inquiries = s.exec(
            select(Inquiry).where(Inquiry.status == InquiryStatus.new)
        ).all()

        # Rate limit: max 5 per run
        for inquiry in new_inquiries[:5]:
            try:
                log.info(f"Auto-search triggered for inquiry {inquiry.id}")
                await run_search_pipeline(inquiry.id)
            except Exception as e:
                log.exception(f"Auto-search failed for inquiry {inquiry.id}: {e}")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    scheduler.add_job(auto_search_job, "interval", minutes=30, id="auto_search")
    scheduler.start()
    log.info("Auto-search scheduler started (runs every 30 minutes)")


@app.on_event("shutdown")
def _shutdown() -> None:
    scheduler.shutdown()


app.include_router(public.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    """Health check endpoint for Railway/monitoring"""
    from sqlmodel import Session, select
    from backend.db import engine
    from backend.models import Settings

    try:
        # Check DB connection
        with Session(engine) as s:
            s.exec(select(Settings).where(Settings.id == 1)).first()

        # Check Anthropic API key configured
        if not config.anthropic_api_key:
            return {"ok": False, "error": "ANTHROPIC_API_KEY not configured"}

        return {"ok": True, "db": "connected", "anthropic": "configured"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
