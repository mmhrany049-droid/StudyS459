# معماری فنی — نسخه ۱

## Stack
Frontend:  
React + Vite + TypeScript + Tailwind

Backend:  
Python + FastAPI + Pydantic + SQLAlchemy

DB:  
SQLite در شروع، PostgreSQL-ready

Integration:  
Telegram Bot API (اختیاری و غیرضروری)

## Backend
app/
- api/
- domain/
- models/
- schemas/
- services/
- repositories/
- analytics/
- planning/
- rewards/
- integrations/   # فقط Telegram اختیاری
- config/
- jobs/
- tests/

API route نباید business logic اصلی را در خود نگه دارد.

## Frontend
src/
- pages/
- components/
- features/
- api/
- hooks/
- types/
- utils/

Features نسخه ۱:
dashboard, planner, tests, progress, books, academics, rewards, settings

## Data Flow
UI → API → Service → Domain → Repository → DB

## Events
TestSessionStarted  
QuestionAnswered  
TestSessionCompleted  
TaskCompleted  
HomeworkCreated  
ExamRecorded  
LessonTaught  
GoalProgressChanged  
RewardEarned  
StreakUpdated

## Security
Authentication ساده + ownership + validation.

## Testing
Unit: selection (range + parity), scoring, analytics, planning, rewards.  
Integration: goal→task→test→attempt→analytics→reward.  
E2E: daily plan→test→result→progress.
