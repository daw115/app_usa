from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from backend.db import init_db
from backend.routes import dashboard, public

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(title="AutoScout US")


@app.on_event("startup")
def _startup() -> None:
    init_db()


app.include_router(public.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"ok": True}
