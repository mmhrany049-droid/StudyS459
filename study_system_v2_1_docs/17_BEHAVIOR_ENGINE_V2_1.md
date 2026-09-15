# موتور رفتار — V2.1

## هدف
یادگیری از رفتار واقعی، نه فقط پاسخ پرسشنامه.

## داده‌های پایه
- study sessions
- completed tasks
- skipped tasks
- task edits
- test results
- actual duration
- wake-up
- breaks
- mood / energy / focus در صورت ثبت
- زمان شروع واقعی

## Featureهای پیشنهادی
```python
features = {
    "task_completion_rate": 0.0,
    "avg_focus_morning": 0.0,
    "avg_focus_evening": 0.0,
    "average_session_minutes": 0.0,
    "late_start_rate": 0.0,
    "hard_task_skip_rate": 0.0,
}
```

## Self Report vs Observed Behavior
اگر کاربر بگوید «صبح بهترین زمان من است» اما داده‌ها نشان دهد شروع مؤثر معمولاً 9 تا 10 است، سیستم باید هر دو را نگه دارد و با confidence نتیجه‌گیری کند.

## Behavioral Memory
داده خام append-only باشد؛ Featureها قابل بازمحاسبه باشند تا تغییر الگوریتم باعث از دست رفتن داده نشود.
