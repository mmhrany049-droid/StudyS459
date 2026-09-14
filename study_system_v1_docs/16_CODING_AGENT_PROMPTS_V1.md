# Promptهای مرحله‌ای عامل کدنویس — نسخه ۱

## Master Prompt
تمام مستندات نسخه ۱ را بخوان.  
هیچ requirement را حدس نزن.  
Domain را از UI/API جدا نگه دار.  
Book hierarchy را hard-code نکن.  
Raw history را overwrite نکن.  
هر schema change با migration.  
هر business rule با test.  
تصمیم‌های Open Decisions را حدس نزن.  
Telegram را اجباری نکن.  
پس از هر phase گزارش changed files، migrations، APIs، UI، tests، acceptance، risks و deferred decisions بده.

## Phase 0 — Foundation
React/Vite/TS/Tailwind + FastAPI/Pydantic/SQLAlchemy + SQLite.  
Config، logging، migrations، health و error envelope.  
هنوز feature business نساز.

## Phase 1 — Book Engine
Subject/Book/BookNode/TestSet/Question/QuestionTopicMap.  
Generic tree.  
Config importer.  
سه کتاب اولیه به صورت config-driven.  
Unit tests برای validation/import.

## Phase 2 — Test Engine
Session/SessionQuestion/Attempt + node_parity_state.  
Range + Odd/Even selection.  
No duplicate داخل session.  
Timed و Untimed.  
Finish idempotent.  
Correct/Wrong/Unanswered مستقل.  
History append-only.  
Insufficient pool handling.

## Phase 3 — Analytics
Coverage/Accuracy/Volume/Topic Progress/Question History/Trends/Weakness ساده.  
Level 1/2/3 حسابان.  
Deterministic + unit tested.

## Phase 4 — Goals
Count/Topic weekly goals.  
Candidate tasks.  
Topic priority.  
No double counting.  
Recommendation reason.

## Phase 5 — Planner
جمعه به عنوان روز اصلی برنامه‌ریزی.  
Schedule-aware capacity.  
School day override.  
Saturday-Wednesday normal.  
Thursday-Friday catch-up.  
User placement.  
Over-capacity warning.

## Phase 6 — Academic
School/external class/class session/taught/homework/exam.  
Taught != learned.  
Homework source.

## Phase 7 — Student State + Rewards
State service از analytics/review/goals/homework/exams/schedule/unfinished.  
امتیاز + streak + نشان.  
Reward events.

## Phase 8 — UI و Hardening
تمام صفحات نسخه ۱.  
Acceptance tests و edge cases.  
سپس polish.

## قانون
در هر prompt فقط همان phase را پیاده کن مگر dependency ضروری باشد.  
Telegram را فقط در صورت درخواست صریح و بعد از نسخه ۱ پایدار اضافه کن.
