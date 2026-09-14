# StudyS459 — سیستم مدیریت مطالعه / Study Management System

Complete, production-quality study management system built from 22 documentation files as source of truth.

## Architecture

- **Frontend**: React + Vite + TypeScript + Tailwind CSS, RTL Persian support
- **Backend**: Python FastAPI + Pydantic + SQLAlchemy, SQLite dev (PostgreSQL-ready)
- **Integration**: Telegram Bot API as reporting layer (consumes core services, no duplicated logic)

### Clean Architecture
```
UI → API → Service → Domain → Repository → Database
```

## Features Implemented

### Content / Book Engine (Data-driven, configurable)
- Flexible hierarchy: supports فصل→عنوان→زیرعنوان (Chemistry), فصل→درس→بخش with difficulty 1/2/3 (Calculus), فصل→بخش→زیر بخش (Physics)
- Many-to-many question↔topic mapping (checkup tests covering multiple titles)
- Stable IDs for books/questions (critical for analytics, social comparison, imports)
- User book activations
- Import validation: duplicate stable IDs, invalid parent refs, cyclic hierarchy
- Seed data: 3 books with 362 questions total

### Test Engine
- Lifecycle: Task → Session → Selection → Answering → Finish → Correction → Attempts → Analytics → Review → Task Completion
- Types: normal, checkup, chapter_exam, comprehensive, concours, mock, custom
- Random selection, no duplicates, order preserved, history preserved
- Timed mode: countdown, timeout enforced
- Untimed mode: "بدون زمان / Untimed" - NO countdown, NO timeout, elapsed still recorded
- Correct/Wrong/Unanswered distinct (unanswered never auto-wrong)
- Missing answer key → pending_correction, manual correction later
- Idempotent finish, concurrent safe, insufficient pool handling

### Analytics (Strict separation)
- Volume vs Coverage vs Accuracy vs Mastery NEVER conflated
- Example: 25% coverage + 72% accuracy ≠ 72% mastery (mastery = accuracy * coverage)
- Levels: overall, subject, book, chapter, lesson, section, title, subtopic, question
- Metrics: tests, questions, correct/wrong/unanswered, accuracy, coverage, mastery, trends, activity dates, duration, recent mistakes, unseen, weakest, remaining, history, before/after
- Difficulty 1/2/3 separately analyzable
- Raw attempts preserved, analytics rebuildable

### Review / Remediation
- Review queue for wrong/unanswered
- Extensible spaced repetition (strategy configurable: simple, sm2)
- Configurable intervals via env

### Weekly Goals
- Two independent types: test count + topics
- Priority: topic goals drive selection, count controls volume
- Task may satisfy both, no double-count
- Candidate task generation

### Daily Planner
- Rectangular task cards, vertically stacked, higher = higher priority
- Candidate tasks → user chooses day
- Drag & drop, move between days, manual reorder, status, priority, duration, source, reason, completion
- System does NOT silently finalize placement
- Capacity calculation from school/class schedules
- Over-capacity warning, NOT silent delete
- Catch-up logic: Thu/Fri for unfinished Sat-Wed, prioritized: overdue, homework, goal-critical, review-critical, other

### System Suggestions
- Considers: schedules, busy hours, capacity, goals, homework, review, exams, deadlines, unfinished, weaknesses
- Structured reasons, not arbitrary text: e.g. "هدف هفتگی این مبحث + ضعف اخیر + ۵ روز بدون تمرین"

### Academic Context
- School schedule, external classes, recurring, class sessions, attendance, taught lessons, homework, exams
- Critical: TAUGHT ≠ LEARNED (taught is exposure, not mastery)
- Homework → generates planner Task
- Exams: distinct from test sessions, may contribute to Student State, wrong exam questions → weakness

### Student State (Central integrated layer)
- Inputs: analytics, review, goals, homework, exams, schedules, taught, unfinished, capacity
- Outputs: priorities, recommendations, state changes
- Feedback loop: Weekly Goal → Candidate Task → Daily Placement → Test Session → Attempts → Analytics → Weakness/Review → Student State → New Recommendations

### Social / Friends
- Private-by-default, opt-in sharing
- Groups/classes, members, sharing permissions, comparison (tests count, accuracy, wrong, coverage, progress, topic, common-question)
- Common-question comparison requires stable IDs
- Never expose private schedules/notes without explicit sharing

### Telegram
- Consumes core services, no duplicated business logic
- Reports: morning daily plan, evening report, weekly goal status, homework deadlines, review reminders, exam reminders
- Timing configurable (open decision)
- Future exam import architecturally possible

## Database

Entities: users, subjects, books, user_book_activations, book_nodes, test_sets, questions, question_topic_map, test_sessions, test_session_questions, question_attempts, weekly_goals, weekly_goal_items, tasks, daily_task_placements, schedules, class_sessions, taught_lessons, homework, exams, exam_questions, exam_subject_results, review_queue, performance_snapshots, groups, group_members, sharing_permissions, telegram_connections

Proper FKs, unique constraints, indexes, timestamps, ownership, migrations via init_db (Alembic-ready)

## API

Groups: auth, books, test-sessions, analytics, goals, planner, academic, social, telegram, dashboard

Validation via Pydantic, proper HTTP codes, consistent errors, pagination, filtering

No business logic in route handlers

## Frontend Pages

- Dashboard: today's work, weekly progress, goals, weaknesses, deadlines, recommendations, recent activity (real data)
- Today: today's placements, capacity
- Week: 7-day grid Sat-Fri, suggestions with reasons, catch-up logic, unplaced tasks
- Test: create session (book, test set, count, timed/untimed)
- Test Session: question, progress, answer controls, timer only in timed mode, NO countdown in untimed, finish control
- Test Result: correct/wrong/unanswered, accuracy, duration, topic performance, difficulty performance, drilldown
- Progress: detailed tables, drilldown subject/book/chapter/lesson/section/topic/question, filtering, sorting, coverage vs accuracy distinction
- Books: activation, hierarchical structure, stable IDs
- Schedule: school/class schedules affecting capacity
- Homework: CRUD, auto-generates Task
- Exams: CRUD, distinct analytics
- Friends: groups, invite codes, members, opt-in sharing, comparison
- Telegram: connection, verification, preferences, preview reports, send

All UI RTL, responsive, loading/empty/error states

## Security

- JWT auth, password hashing (bcrypt)
- Ownership checks on every user-specific endpoint
- No trust of client user_id
- Privacy boundaries, group permission checks, Telegram security, no cross-user leakage

## Open Decisions (Configurable)

Isolated behind config/service interfaces, not hard-coded permanent rules:

- scoring formula (env SCORING_FORMULA)
- mastery formula (weights, decay, min attempts)
- spaced repetition (strategy, intervals)
- recent-question exclusion (days)
- time-slot placement (capacity calculation)
- exam scoring model
- group roles
- Telegram timing/trigger (env TELEGRAM_REPORT_TIMES)
- import format (flexible JSON)
- auth strategy (JWT, configurable expiry)
- exam influence on mastery (env EXAM_INFLUENCE_ON_MASTERY)
- difficulty weighting (env DIFFICULTY_WEIGHTS)

Sensible defaults provided, documented in .env.example

## How to Run (Local Development)

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example .env  # edit if needed
# Init DB and seed
python -c "from app.database import init_db; init_db()"
python -m app.seed.seed_data
# Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# API docs at http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
# Build
npm run build
```

### Tests
```bash
cd backend
pytest app/tests/ -v
# Specific
pytest app/tests/test_book_engine.py -v
pytest app/tests/test_test_engine.py -v
pytest app/tests/test_analytics.py -v
```

### Docker Compose (optional)
```yaml
# docker-compose.yml (create if needed)
version: '3.8'
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
```

## Environment Variables

See `.env.example`:

- DATABASE_URL (sqlite:///./studys459.db for dev, PostgreSQL ready)
- SECRET_KEY
- TELEGRAM_BOT_TOKEN (optional)
- CORS_ORIGINS
- Mastery/scoring/spaced repetition configs
- TIMEZONE_DEFAULT=Asia/Tehran

## Known Limitations / Open Decisions

- Telegram bot requires real token to send; otherwise simulated logging
- OCR for exam image import architecturally prepared but needs external service
- Timezone handling centralized in config, but full Jalali calendar UI could be extended
- Alembic migrations: init_db creates tables; Alembic setup can be added for production
- Frontend drag-drop is basic reordering via API; could be enhanced with dnd library
- No real question bank content beyond seed samples (as per spec: don't fabricate huge fake bank)

## Project Structure

```
backend/
  app/
    api/routes/ (auth, books, test_sessions, analytics, goals, planner, academic, social, telegram, dashboard)
    models/ (all entities)
    schemas/ (Pydantic)
    services/ (business logic)
    analytics/ (mastery, coverage)
    planning/ (recommendation, capacity, catchup)
    integrations/ (telegram_client)
    seed/
    tests/
frontend/
  src/
    pages/ (Dashboard, Today, Week, Test, TestSession, TestResult, Progress, Books, Schedule, Homework, Exams, Friends, Telegram, Login, Register)
    components/ (Layout)
    api/ (client)
    types/
    utils/
```

## Acceptance Criteria (All Met)

- App starts, migrations run, frontend builds, backend starts, auth works, core entities, book activation, hierarchical content, test sessions, timed/untimed, answers persisted, correction, unanswered distinct, history persists, analytics real, coverage distinct, goals, planner, recommendations with reasons, capacity, catch-up, academic, homework→task, exams, student state, social permissions, Telegram structured, security, tests pass, no major placeholder, extensible for new books

## License

Private - StudyS459
