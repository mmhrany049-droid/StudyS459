# API Blueprint

Commands should mutate raw/user-decision data; queries should not mutate data.

Representative commands:
POST /questions
POST /questions/:id/topic-mappings
POST /questions/:id/answer-key
POST /test-sessions
POST /response-sheets/:id/entries
POST /test-sessions/:id/submit
POST /topics/:id/taught
POST /exams
POST /mock-exams
POST /goals
POST /activities
POST /study-tasks
POST /study-tasks/:id/complete
POST /planning/generate
POST /planning/:id/finalize
POST /recommendations/:id/accept|reject|adjust
POST /recalculations

Queries include dashboard, topic state/history, priorities, review queue, upcoming exams, goals/progress, calendar, capacity, duration estimate, planning session and recommendation explanation.

Generated plans should return priorities, adaptive questions, capacity, tasks, duration ranges, explanations, confidence and model versions.
