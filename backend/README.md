# SS459 Backend (Phase 0 — Foundation)

FastAPI + Pydantic + SQLAlchemy. SQLite by default, PostgreSQL-ready.

> Phase 0 contains **no business features** — only config, logging,
> migrations, health checks and the standard error envelope (spec 16).

## Quickstart

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # optional (defaults work out of the box)

alembic upgrade head   # apply migrations (baseline in Phase 0)
uvicorn app.main:app --reload --port 8000
```

- Health: `GET http://localhost:8000/health`
- DB check: `GET http://localhost:8000/health/db`
- API docs: `http://localhost:8000/docs`

## Tests

```bash
pytest -q
```

## Migrations

```bash
alembic upgrade head          # apply
alembic downgrade -1          # roll back one
alembic revision --autogenerate -m "add books"   # new migration (Phase 1+)
```

Every schema change ships with a migration (spec 16 master prompt).
The DB URL always comes from `DATABASE_URL` (single source of truth);
override per run with `alembic -x db_url=<URL> ...`.

## Structure (spec 12)

```
app/
  main.py          # app factory, middleware, exception handlers
  config.py        # env-based settings (TIMEZONE=Asia/Tehran)
  logging_config.py# text/json logging
  errors.py        # AppError + error envelope
  db.py            # engine / session / Base
  api/             # routes only — NO business logic here
    deps.py        # shared deps (temporary single-user id)
    v1/            # code versioning; URLs follow the contract verbatim
  domain/ models/ schemas/ services/ repositories/
  analytics/ planning/ rewards/ integrations/ jobs/
```

Data flow: `UI → API → Service → Domain → Repository → DB`.

## Error envelope

All errors (4xx/5xx) return:

```json
{"error": {"code": "not_found", "message": "...", "details": null}}
```

Success (2xx) responses return the payload directly.

## PostgreSQL

```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ss459 alembic upgrade head
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ss459 uvicorn app.main:app
```
