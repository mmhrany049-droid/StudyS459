"""SS459 — نقطهٔ ورود FastAPI.

API زیر /api و رابط کاربری (build شدهٔ React) از /.
برنامه بدون Telegram کامل کار می‌کند (اختیاری و غیرضروری — پیاده نشده).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import SessionLocal, engine
from app.models import Base
from app.seed import seed_all

from app.api import analytics, core, intelligence, planner, tests

app = FastAPI(title="SS459 — Study System", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # تک‌کاربره؛ dev سرور Vite روی پورت دیگر
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(core.router, prefix="/api")
app.include_router(tests.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(planner.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True, "version": "2.1"}


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()


# ------------------------------- UI (SPA) ------------------------------------

DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "frontend", "dist")

if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api"):
            from fastapi import HTTPException
            raise HTTPException(404, "مسیر API پیدا نشد.")
        candidate = os.path.join(DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST, "index.html"))
