# مشخصات پایگاه داده — نسخه ۱

## Core
### users
id, username, display_name, grade, track, timezone, total_points, current_streak, longest_streak, created_at, updated_at

### subjects
id, name, grade, track, type

### books
id, stable_key, title, publisher, subject_id, grade, track, edition, config_version

### user_book_activations
user_id, book_id, active, activated_at

### book_nodes
id, book_id, parent_id, node_type, title, code, order_index, metadata_json

### test_sets
id, book_id, title, test_type, node_id nullable, metadata_json

### questions
id, book_id, stable_key, test_set_id, sequence_no, difficulty_level nullable, answer_type, answer_key, metadata_json

### question_topic_map
question_id, node_id

### node_parity_state
id, user_id, node_id, last_parity (odd/even), last_used_at

## Test
### test_sessions
id, user_id, task_id nullable, timed, time_limit_seconds nullable, sequence_from, sequence_to, parity, started_at, ended_at, status

### test_session_questions
session_id, question_id, display_order

### question_attempts
id, session_id, question_id, user_id, answer, result, answered_at, response_time_seconds nullable

## Planning
### weekly_goals
id, user_id, week_start, week_end, active

### weekly_goal_items
id, goal_id, goal_type, target_value, subject_id nullable, book_id nullable, node_id nullable

### tasks
id, user_id, task_type, title, source_type, source_id, priority, estimated_minutes, due_at, status, recommendation_reason, created_at

### daily_task_placements
task_id, date, position

## Academic
### schedules
id, user_id, schedule_type, title, day_of_week, start_time, end_time, recurring, source

### school_day_overrides
id, user_id, date, is_school_day, reason, created_at

### class_sessions
id, user_id, schedule_id, date, subject_id, attended, notes

### taught_lessons
id, user_id, class_session_id nullable, subject_id, node_id nullable, taught_at, duration_minutes, notes

### homework
id, user_id, source_type, title, subject_id, node_id nullable, due_at, estimated_minutes, priority, status

### exams
id, user_id, title, exam_type, provider, exam_date, total_questions, total_score, images_metadata

### exam_questions
id, exam_id, sequence_no, question_id nullable, topic_node_id nullable, answer_key, user_answer, result

### exam_subject_results
id, exam_id, subject_id, correct_count, wrong_count, unanswered_count, percentage, score

## Analytics
### review_queue
id, user_id, entity_type, entity_id, reason, priority, scheduled_for, status, created_at

### performance_snapshots
id, user_id, scope_type, scope_id, snapshot_date, attempted, correct, wrong, unanswered, accuracy, coverage

## Reward
### reward_events
id, user_id, event_type, points, description, related_entity_type, related_entity_id, created_at

### badges
id, code, title, description, condition_type, condition_value

### user_badges
user_id, badge_id, earned_at

## Integration (اختیاری)
### telegram_connections
id, user_id, chat_id, enabled, settings_json, created_at

## اصول
- history append-only
- stable IDs
- ownership
- migrations
- indexes روی user_id، book_id، node_id، question_id و تاریخ‌ها
