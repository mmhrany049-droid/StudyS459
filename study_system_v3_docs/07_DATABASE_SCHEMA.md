# Database Schema Blueprint

Core tables:
users, subjects, books, topics, topic_dependencies, questions, question_topics, answer_key_versions, test_sessions, response_sheets, response_entries, attempt_results, classes, taught_topics, activities, study_tasks, task_executions, exams, exam_topics, goals, goal_milestones, goal_objectives, learning_states, review_items, priority_snapshots, planning_sessions, planning_questions, planning_answers, recommendations, capacity_snapshots, duration_predictions, duration_observations, behavior_observations, user_states, behavior_patterns, experiments, experiment_observations, experiment_results, audit_events, recalculation_jobs.

Important fields include stable IDs, timestamps, model versions, status, source and JSON evidence/reasons where appropriate.

Rules: preserve raw observations; derived tables are rebuildable; historical attempts are append-oriented; model versions accompany derived values; topic dependency cycles should be rejected; missing values need explicit semantics.
