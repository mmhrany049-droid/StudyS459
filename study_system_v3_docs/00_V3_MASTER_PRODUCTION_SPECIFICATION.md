# StudyS459 V3 — Master Production Specification

## Purpose
This is a self-contained source of truth for an AI coding agent. It consolidates the V1/V2/V2.1/V2.2 concepts plus the V3 requirements. The coding agent must not require previous conversations or documents.

## Product
StudyS459 V3 is a personal adaptive study-management and learning-intelligence system. It connects books, topics, questions, answer keys, response sheets, attempts, taught topics, learning state, exams, goals, activities, capacity, planning, execution and feedback.

Core loop:
`INPUT → MODEL → DECIDE → PLAN → EXECUTE → OBSERVE → LEARN → REPLAN`

Complexity belongs inside the engine; the UI remains simple.

## Existing content
The repository contains study specifications/content for:
- Physics 2 — خیلی سبز
- Calculus 1 — نشر الگو
- Chemistry 2 — مبتکران

Existing content should be migrated rather than discarded.

## Architecture
Presentation → Application Services → Domain/Intelligence → Data Access → Database.

Do not implement a literal neural network just because the system is described as interconnected like one. Use a Learning Graph plus modular decision engines, interpretable/statistical models and feedback loops.

## Data layers
1. Raw Data: actual facts (selected answer, actual duration, taught checkbox, exam date).
2. Derived Data: accuracy, coverage, retention estimate, confidence, priority, duration estimate.
3. System Decisions: recommendations and generated plans.
4. User Decisions: overrides, accept/reject/adjust actions.

Never mix these layers.

## Topic model
Hierarchy:
Subject → Book → Chapter → Section → Subsection → Fine Topic

Separate dependency graph:
Topic A → prerequisite → Topic B

A question may have:
- primary topic;
- related topics;
- prerequisite topics;
- solution-used topics.

Topic mapping must be correctable.

## Taught Topics
Taught means the user has been exposed/taught a topic. It does not mean learned/mastered.

Taught status is checkbox-based and cascades through chapter/section/subsection levels. Parent states may be checked, unchecked or indeterminate.

Taught status affects practice eligibility.

## Question semantics
### Question Definition
What the question is and where it belongs.

### Answer Key
The objectively correct answer. Version it when corrected.

### Response Sheet
The user's answers for one specific test sitting.

### Attempt Result
Comparison of Response Entry with Answer Key.

Mandatory distinct states:
- ANSWERED
- UNANSWERED
- NOT_ENTERED

NOT_ENTERED = historical response has not yet been entered.
UNANSWERED = user actually left it blank.

## Test Sessions
A TestSession represents one actual solving event. Store type, dates, planned/actual duration, questions, source and links to task/exam.

Historical attempts are append-oriented. Repeating a question creates another attempt.

## Learning State
Do not reduce weakness to wrong-count. Track dimensions such as:
- accuracy;
- coverage;
- confidence;
- retention;
- recency;
- difficulty-adjusted performance;
- repeated-error signal;
- time performance;
- exam readiness;
- prerequisite health.

Confidence measures reliability of the estimate.

## Review and intervention
First choose WHY/WHAT KIND of intervention is needed, then select questions.

Interventions may include:
READ_LESSON, REVIEW, ACTIVE_RECALL, EASY_PRACTICE, MEDIUM_PRACTICE, DIFFICULT_PRACTICE, MIXED_PRACTICE, TIMED_QUIZ, DIAGNOSTIC, MOCK_EXAM, PREREQUISITE_REVIEW, ERROR_REVIEW.

Retrieval, spacing, interleaving and related learning principles may inform the engine. Exact numeric schedules must be configurable and evidence-validated.

## Recommendation engine
Consider:
- exam relevance;
- long-term goal relevance;
- taught eligibility;
- learning need;
- coverage need;
- accuracy need;
- review need;
- retention risk;
- recency;
- prerequisites;
- difficulty fit;
- available time;
- behavioral fit;
- time-of-day evidence;
- historical response to interventions.

Old Range + Parity logic may remain as a small question-selection signal, not the main intelligence.

## Priority engine
Priority answers WHAT matters. Recommendation answers WHAT to do. Planner answers WHEN.

Conceptual priority:
Exam Need + Goal Need + Learning Need + Coverage Need + Review Need + Prerequisite Need + Retention Risk + Behavioral Fit + Opportunity − Capacity Cost − Recent Saturation.

Weights are configurable and must be tested.

Before weekly planning, show a recommendation such as:
“These topics deserve more attention this week.”
User can Accept / Increase / Decrease / Reject / Add another.
Store this feedback as data.

## Exams
School exams and mock exams are first-class future-oriented events.

Mock exam stores:
- date/time;
- type;
- subjects;
- planned topics;
- actual topics;
- planned/actual question count;
- planned/actual duration;
- status;
- preparation relationship;
- retake relationship.

Planned and actual topic coverage are separate.

Upcoming exams raise relevant priority but must not erase long-term goals, review, capacity or other important constraints.

## Long-term goals
Support approximately three-month goals such as improving a subject from current state to a target state.

Decompose:
3-month goal → month → week → day → task.

Track baseline, target, milestones, current state, coverage/accuracy/readiness progress and confidence.

## Activities vs Study Tasks
Activity = occupies time/availability:
sport, gym, work, appointment, family, school, commute, rest, travel.

Study Task = work to perform.

Activities are constraints, not failed study tasks.

Support fixed/preferred/flexible/deadline-only scheduling.

## Capacity
Capacity is realistic completion capability, not theoretical free hours.

Use historical completion, actual durations, activities, workload, difficulty, state and exams.

Avoid chronic over-planning.

## Time estimation
For approximately the first month:
- do not ask user to predict task duration;
- ask after completion how long it actually took;
- use a rough 60–120 minute range for test sessions when needed.

After sufficient evidence:
- personalize duration;
- return ranges such as 65–82 minutes;
- attach confidence;
- model subject/topic/task type/question count/difficulty/time-of-day/state;
- detect systematic changes instead of using one global average.

## Weekly planner
Pipeline:
1. load context;
2. analyze exams;
3. analyze goals;
4. check taught topics;
5. calculate learning state;
6. calculate review;
7. calculate priority;
8. show priority suggestions;
9. ask only high-value adaptive questions;
10. estimate capacity;
11. select interventions;
12. estimate duration;
13. allocate work;
14. balance exam/goal/review/coverage;
15. detect overload;
16. explain;
17. generate plan;
18. let user edit;
19. finalize and save.

Show a planning animation with meaningful stages.

## Adaptive interview
Do not use a fixed long questionnaire. Ask only when uncertainty can materially change a decision. Stop when uncertainty is resolved.

## Manual override
User can move, delete, add, resize, reprioritize and defer tasks. Auto-planner must not silently undo manual edits.

## Recovery
If tasks are missed:
- recalculate;
- protect critical work;
- distribute remaining work;
- defer low-value work;
- respect new constraints.

Never dump all missed tasks onto the next day.

Illness, travel, exams and events are constraints/context, not automatic failure.

## Behavior and state
Track observed and inferred state separately. Potential dimensions:
energy, focus, stress, motivation, confidence, fatigue, mental capacity.

Do not turn short-term behavior into permanent personality labels.

## Personal experiments
Support hypotheses such as:
“Starting a difficult session with 10 easy questions improves completion.”

Store hypothesis, intervention/control, measurements, observations, result and confidence. One successful session is not proof.

## Explainability
Every major recommendation should expose:
- What?
- Why?
- Evidence?
- What can I change?

Never use “AI says so” as the explanation.

## Recalculation and integrity
If answer key, topic mapping, taught state or other source data changes:
- preserve audit history;
- recalculate affected attempt results;
- recalculate accuracy/coverage/learning state;
- recalculate priorities/recommendations when needed.

Support incremental and full rebuilds. Version important models.

## Research
Relevant areas include retrieval practice, spacing, interleaving, metacognition, desirable difficulties, knowledge tracing, forgetting/retention, adaptive learning, cognitive load, adherence and time-on-task estimation.

Fresh web research was not performed while creating this package. Research-specific production rules and numerical parameters must therefore be independently verified before being hard-coded.

## Core entities
User, Subject, Book, Topic, TopicDependency, Question, QuestionTopic, AnswerKey, AnswerKeyVersion, TestSession, ResponseSheet, ResponseEntry, AttemptResult, Class, TaughtTopic, Activity, StudyTask, TaskExecution, Exam, ExamTopic, MockExam, SchoolExam, Goal, GoalMilestone, GoalObjective, LearningState, CoverageMetric, AccuracyMetric, RetentionState, ConfidenceState, ReviewItem, Recommendation, RecommendationReason, PrioritySnapshot, PlanningSession, PlanningQuestion, PlanningAnswer, CapacitySnapshot, DurationPrediction, DurationObservation, BehaviorObservation, UserState, BehaviorPattern, Experiment, ExperimentObservation, ExperimentResult, Notification, Reward, Habit, AuditEvent, RecalculationJob.

## Implementation order
1. Foundation/database/calendar/migration.
2. Question/Answer Key/Response Sheet/Attempts.
3. Learning State/Coverage/Accuracy/Review/Dependencies.
4. School/Mock Exams.
5. Goals/Milestones.
6. Activities/Capacity.
7. Priority/Intervention/Duration/Planner.
8. Behavioral intelligence/experiments.
9. Analytics/explainability.
10. Optional integrations.

## Non-negotiable rules
- taught ≠ learned;
- activity ≠ study task;
- priority ≠ schedule;
- recommendation ≠ task;
- question ≠ answer key;
- answer key ≠ response sheet;
- not-entered ≠ unanswered;
- raw ≠ derived;
- one error ≠ weakness;
- one success ≠ mastery;
- free time ≠ capacity;
- missed task ≠ failure;
- accepted recommendation ≠ proof of quality;
- no false precision;
- no silent data corruption.
