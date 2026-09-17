# Domain Model

Defines semantic boundaries for User, Subject, Book, Topic, TopicDependency, Question, AnswerKey, TestSession, ResponseSheet, AttemptResult, TaughtTopic, LearningState, Exam, Goal, Activity, StudyTask, Recommendation and PlanningSession.

Key invariants:
1. ResponseSheet never redefines Question.
2. AttemptResult uses ResponseEntry + applicable AnswerKey version.
3. Taught never implies mastery.
4. LearningState is derived/rebuildable.
5. Attempts are append-oriented.
6. Activity is not StudyTask.
7. Recommendation is not Task.
8. Priority is not Schedule.
9. User override is not raw observation.
10. Missing data is not silently zero.
