from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config.settings import settings
from .database import init_db
from .api.routes import auth, books, test_sessions, analytics, goals, planner, academic, social, telegram, dashboard, review, progress

app = FastAPI(
    title="StudyS459 - Study Management System",
    description="Complete study management system with books, test engine, analytics, planning, academic context, social, telegram",
    version="1.0.0"
)

# CORS
origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(books.router, prefix="/api")
app.include_router(test_sessions.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(progress.router, prefix="/api")
app.include_router(review.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(planner.router, prefix="/api")
app.include_router(academic.router, prefix="/api")
app.include_router(social.router, prefix="/api")
app.include_router(telegram.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def root():
    return {"message": "StudyS459 API", "version": "1.0.0", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}
