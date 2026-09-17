"""StudyS459 V3 — application entrypoint.

Layer separation is enforced here: routers → services → domain → repositories
(SQLAlchemy) → database. API routes never contain business logic and the
presentation layer never computes a derived value on its own.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from . import config
from .api.routers import (
    analytics,
    calendar as calendar_router,
    curriculum,
    exams,
    goals,
    imports,
    lab,
    planning,
    questions,
    system,
    testing,
)
from .core.errors import DomainError
from .core.text import fa_text_deep
from .db import models
from .db.base import get_session_factory, init_db
from .db.seed import seed_all

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend")
FRONTEND_DIR = os.path.normpath(FRONTEND_DIR)

class PersianJSONResponse(JSONResponse):
    """One place where the Persian-only rule is enforced for outgoing prose.

    Data stays numeric; only human-readable strings get Persian digits, so the
    UI can never show a Gregorian-looking number or a Latin digit in Persian text.
    """

    def render(self, content: object) -> bytes:  # type: ignore[override]
        return super().render(fa_text_deep(content))


app = FastAPI(
    title="StudyS459 V3",
    description=(
        "سیستم شخصی مدیریت مطالعه و هوش یادگیری. "
        "معماری: Presentation → Application Services → Domain/Intelligence → Data Access → Database."
    ),
    version=config.MODEL_VERSION,
    default_response_class=PersianJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content={"error": exc.as_dict()})


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "ورودی نامعتبر است.", "details": exc.errors()}},
    )


for router in (
    system.router,
    curriculum.router,
    questions.router,
    testing.router,
    imports.router,
    planning.router,
    exams.router,
    goals.router,
    analytics.router,
    lab.router,
    calendar_router.router,
):
    app.include_router(router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    if os.environ.get("STUDYS459_AUTOSEED", "1") == "1":
        session = get_session_factory()()
        try:
            user = session.scalars(select(models.User).order_by(models.User.id)).first()
            if user is None:
                from .services.common import create_user

                user = create_user(session, "دانش‌آموز", "me")
            seed_all(session, user)
            session.commit()
        except Exception:  # pragma: no cover - startup must never crash the app
            session.rollback()
        finally:
            session.close()


@app.get("/api")
def api_root() -> dict:
    return {
        "app": "StudyS459 V3",
        "version": config.MODEL_VERSION,
        "docs": "/docs",
        "principles": [
            "تدریس‌شده ≠ یادگرفته‌شده",
            "فعالیت ≠ کار مطالعه",
            "اولویت ≠ برنامه زمانی",
            "پیشنهاد ≠ کار",
            "سؤال ≠ پاسخ‌نامه",
            "پاسخ‌نامه ≠ پاسخ‌برگ",
            "ثبت‌نشده ≠ نزده",
            "داده خام ≠ داده مشتق",
            "یک خطا ≠ ضعف",
            "یک موفقیت ≠ تسلط",
            "وقت آزاد ≠ ظرفیت",
            "کار انجام‌نشده ≠ شکست",
        ],
    }


def mount_frontend(application: FastAPI) -> None:
    if not os.path.isdir(FRONTEND_DIR):
        return
    application.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


mount_frontend(app)
