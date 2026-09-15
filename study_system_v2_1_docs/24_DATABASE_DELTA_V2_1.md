# تغییرات دیتابیس — V2.1

تمام schema changeها migration داشته باشند.

## جداول/فیلدهای جدید پیشنهادی
### user_profile
- user_id
- personality_json
- preferences_json
- version
- updated_at

### behavior_events
- id
- user_id
- event_type
- event_time
- payload_json
- source

### user_state_snapshots
- id
- user_id
- captured_at
- energy
- focus
- motivation
- stress
- fatigue
- readiness
- confidence_json

### planning_interviews
- id
- user_id
- week_start
- answers_json
- created_at
- model_version

### task_planning_metadata
- task_id
- source
- manual_override
- override_reason
- planner_version
- evidence_json

## حفظ V2
تمام فیلدها/جداول V2 حفظ شوند:
- is_imported
- actual_duration_minutes
- auto_time_adjust_applied
- wake_up_events
- default seed source
- node_parity_state
- review_queue
- rewards
- weekly_goals
- tasks
- school_day_overrides
