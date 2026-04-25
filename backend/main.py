from __future__ import annotations

import asyncio
import logging
import sys
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from backend.config import config
from backend.db import engine, init_db
from backend.models import Inquiry, InquiryStatus, Settings
from backend.routes import dashboard, public
from backend.tasks import run_search_pipeline


def _setup_logging() -> None:
    """Configure logging — JSON format in production (Railway), text locally."""
    handler = logging.StreamHandler(sys.stdout)
    if config.log_format == "json":
        from pythonjsonlogger import jsonlogger
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] — %(message)s"
        )
    handler.setFormatter(formatter)

    root = logging.root
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


_setup_logging()
logging.root.addFilter(RequestIDFilter())
log = logging.getLogger(__name__)


# Sentry init (only if DSN configured)
if config.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=config.sentry_dsn,
        environment=config.environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    log.info("Sentry initialized for environment=%s", config.environment)

# Validate critical env vars
if not config.anthropic_api_key:
    raise RuntimeError("ANTHROPIC_API_KEY is required in .env")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AutoScout US")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    # Add to logging context
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id
        return record
    logging.setLogRecordFactory(record_factory)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    # Restore factory
    logging.setLogRecordFactory(old_factory)
    return response

scheduler = AsyncIOScheduler()


async def auto_search_job():
    """Auto-search for new inquiries every 30 minutes"""
    job_id = str(uuid.uuid4())[:8]

    # Set logging context for background job
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = f"job-{job_id}"
        return record
    logging.setLogRecordFactory(record_factory)

    try:
        with Session(engine) as s:
            settings = s.exec(select(Settings).where(Settings.id == 1)).first()
            if not settings or not settings.auto_search_enabled:
                log.info("Auto-search disabled in settings")
                return

            # Find new inquiries
            new_inquiries = s.exec(
                select(Inquiry).where(Inquiry.status == InquiryStatus.new)
            ).all()

            if not new_inquiries:
                log.info("No new inquiries to process")
                return

            log.info(f"Auto-search: Processing {len(new_inquiries)} new inquiries (max 5)")

            # Rate limit: max 5 per run
            for inquiry in new_inquiries[:5]:
                try:
                    log.info(f"Auto-search triggered for inquiry {inquiry.id}")
                    await run_search_pipeline(inquiry.id)
                except Exception as e:
                    log.exception(f"Auto-search failed for inquiry {inquiry.id}: {e}")
    finally:
        logging.setLogRecordFactory(old_factory)


async def cache_cleanup_job():
    """Clean up expired cache entries every hour"""
    from backend.services.cache import get_cache
    cache = get_cache()
    cache.cleanup_expired()
    stats = cache.stats()
    log.info(f"Cache cleanup complete: {stats}")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    scheduler.add_job(auto_search_job, "interval", minutes=30, id="auto_search")
    scheduler.add_job(cache_cleanup_job, "interval", hours=1, id="cache_cleanup")
    scheduler.start()
    log.info("Schedulers started: auto-search (30min), cache cleanup (1h)")


@app.on_event("shutdown")
def _shutdown() -> None:
    scheduler.shutdown()


app.include_router(public.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    """Health check endpoint for Railway/monitoring.

    Returns 200 only if all checks pass. Railway treats non-2xx as unhealthy.
    """
    from sqlmodel import Session, select
    from backend.db import engine
    from backend.models import Settings

    try:
        with Session(engine) as s:
            s.exec(select(Settings).where(Settings.id == 1)).first()
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "db": "down", "error": str(e)},
        )

    if not config.anthropic_api_key:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "ANTHROPIC_API_KEY not configured"},
        )

    return {"ok": True, "db": "connected", "anthropic": "configured"}


@app.get("/api/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    from backend.services.cache import get_cache
    cache = get_cache()
    return cache.stats()
