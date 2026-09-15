# تغییرات دیتابیس نسخه ۲

## فیلدها / جداول جدید یا گسترش
- test_sessions.is_imported (bool, default false)
- test_sessions.actual_duration_minutes (nullable)
- test_sessions.auto_time_adjust_applied (bool, optional)
- users.habit_learning_started_at / active_study_days_count (یا محاسبه از events)
- wake_up_events: user_id, date, recorded_at, points_awarded
- class seed flag روی schedules (source=default_seed_v2)

## حفظ شده از V1
node_parity_state، review_queue، rewards، weekly_goals، tasks، school_day_overrides
