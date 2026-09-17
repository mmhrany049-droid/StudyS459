# Migration Specification

Pipeline: legacy extraction → normalization → mapping → validation → V3 import → derived-data rebuild.

Migrate useful V1/V2/V2.1/V2.2 concepts: books/topics, questions, tests, sessions, attempts, planner/tasks, classes/homework/exams, review, rewards/streaks, Jalali dates, taught topics and mock exams.

Question Definitions, Answer Keys, Response Sheets, Attempts, Taught Topics, Study Tasks, Activities, Exams and Goals should receive V3 semantics.

Preserve raw history. Rebuild stale derived metrics. Back up legacy data. Migration should be repeatable/idempotent or use a ledger.
