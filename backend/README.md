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

## Book Engine (Phase 1)

Config-driven books (spec 05): `book_configs/*.json` + `POST /books/import`.
Schema, rules and sample-data warnings: [`book_configs/README.md`](book_configs/README.md).

```bash
# Import the three sample books (idempotent — re-runs are no-ops):
for f in book_configs/*.json; do
  curl -s -X POST localhost:8000/books/import -H 'Content-Type: application/json' -d @"$f"
  echo
done
curl -s localhost:8000/books | head -c 400; echo
```

Key endpoints: `GET /books`, `GET /books/{id}`, `POST /books/import`,
`POST|DELETE /users/me/books/{id}/activate`,
`GET /books/{id}/nodes`, `GET /nodes/{id}/children`.
Deactivation never deletes history (spec 05/13).

## Test Engine (Phase 2)

Range + odd/even selection (spec 06). Pool = questions mapped to the node
**or any descendant**; random sample without replacement; no partial sessions.

```bash
# 6 odd questions from node 2 (chem ch1_t1 after importing chem2):
curl -s -X POST localhost:8000/test-sessions -H 'Content-Type: application/json' \
  -d '{"node_id":2,"count":6,"parity":"odd"}' | head -c 300; echo
```

Key endpoints: `POST /test-sessions`, `GET /test-sessions/{id}`,
`POST /test-sessions/{id}/answers` (append-only, `client_attempt_id` idempotent),
`POST /test-sessions/{id}/finish` (idempotent),
`POST /test-sessions/{id}/corrections` (pending only),
`GET /nodes/{id}/parity-state` (last + suggested parity).

Rules enforced: insufficient pool -> `422 insufficient_questions` (no session,
Persian message + counts); timed requires `time_limit_seconds > 0`; untimed
forbids it; timeout auto-completes with `ended_at = deadline` (deterministic);
answer keys never leak to clients; sessions on inactive books -> `409`.

## Analytics (Phase 3)

Live computation from finalized attempts (spec 07); no snapshot tables in v1.

```bash
curl -s localhost:8000/progress/overview | head -c 300; echo
```

Key endpoints: `GET /progress/overview` (global = ACTIVE books only),
`GET /progress/books/{id}` (topic table, every node incl. chapters),
`GET /progress/nodes/{id}` (drill-down), `GET /progress/questions/{id}`
(full append-only history), `GET /analytics/trends?days=&group_by=day|week`
(user timezone, weeks start Saturday), `GET /analytics/weaknesses?limit=&min_volume=`.

Definitions: volume = finalized question-instances; coverage = distinct
questions seen in FINISHED sessions / pool (in-progress excluded);
accuracy = correct / (correct + wrong), pending never counted. Weakness
score = (wrong + 0.5 x unanswered) / volume; all-correct topics are hidden.
Finish/correction populate `review_queue` (wrong -> high, unanswered -> normal,
one open row per question+reason).

## Goals (Phase 4)

Weekly count/topic goals (spec 02/08). Progress is always derived from
finalized attempts (never stored counters).

```bash
curl -s localhost:8000/goals/weeks/2026-09-12 | head -c 300; echo
```

Key endpoints: `GET/POST /goals/weeks/{week}` (any day resolves to its
Saturday..Friday week), `PATCH /goals/{id}` (mid-week adjustment),
`GET /goals/{id}/candidate-tasks` (computed suggestions, not stored).

Rules: count target = positive int (questions); topic target = coverage
fraction (0,1] with required `node_id`; one goal per user+week (`409` on
duplicate); week totals count every instance ONCE (no double-count);
candidates merge goal/weakness/review sources with a Persian
`recommendation_reason`; inactive books yield progress but no candidates;
tasks/placements tables arrive with the Planner (Phase 5).

## Planner (Phase 5)

Tasks + user-owned placements + capacity (spec 02/08). Friday plans the
Sat..Fri week; mid-week edits stay valid till Friday.

```bash
curl -s localhost:8000/planner/day/2026-09-12 | head -c 300; echo
```

Key endpoints: `POST /tasks` (test pins node/count/range/parity),
`PATCH /tasks/{id}` (validated status transitions), `POST
/tasks/{id}/complete` (idempotent), `PUT /planner/placements` (wholesale
replace per date present; `dates` can clear a day), `GET
/planner/day/{date}`, `GET /planner/week/{week}` (days + unplaced +
catch-up queue), `POST /school-day-overrides`.

Rules: Sat..Wed school days (90 min), Thu/Fri free (240 min); override
flips any date («مدرسه نمی‌روم»); workload sums OPEN tasks only;
over-capacity warns with a breakdown and never deletes; finishing a
linked test session auto-completes its task; `homework`/`exam` task
sources activate in Phase 6.

## Academic (Phase 6)

Schedules, class sessions, taught lessons, homework, exams (spec 09).

```bash
curl -s localhost:8000/exams | head -c 300; echo
```

Key endpoints: `GET/POST /schedules` (weekly recurring or one-off with a
date), `GET/POST /class-sessions`, `GET/POST /taught-lessons`
(record-only: taught != learned, zero analytics effect), `GET/POST
/homework` + `PATCH /homework/{id}` (optional task creation; done
completes the linked task), `GET/POST /exams`, `GET /exams/{id}`, `POST
/exams/{id}/questions` (duplicate-safe upsert by sequence), `GET
/exams/{id}/analytics` (counts only).

Rules: scheduled class minutes shrink day capacity (school rows only on
school days; external always; floor 0); exam analytics never compute
percentages or scores (open decisions #1/#6), so `exam_subject_results`
is deliberately not built; capacity has no summer exception (rule 7).

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
