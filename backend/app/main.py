from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config as cfg
from .api import books, exams_api, study
from .db import Base, SessionLocal, engine
from .seed.seeder import bootstrap


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        bootstrap(db)
    yield


app = FastAPI(title=cfg.APP_NAME, version=cfg.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(study.router)
app.include_router(exams_api.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": cfg.APP_VERSION, "name": cfg.APP_NAME}


@app.get("/api/meta")
def meta():
    return {
        "version": cfg.APP_VERSION,
        "limits": {
            "image_max_mb": cfg.EXAM_IMAGE_MAX_BYTES // (1024 * 1024),
            "pdf_max_mb": cfg.EXAM_PDF_MAX_BYTES // (1024 * 1024),
            "review_max_per_session": cfg.REVIEW_MAX_QUESTIONS_PER_SESSION,
        },
        "question_tags": list(cfg.QUESTION_TAGS),
        "weekdays": ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه"],
    }


# ---------------- serve built frontend (production) ----------------
_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
