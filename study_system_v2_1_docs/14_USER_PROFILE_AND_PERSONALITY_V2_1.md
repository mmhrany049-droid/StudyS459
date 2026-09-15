# مدل کاربر و شخصیت — V2.1

## هدف
ساخت یک مدل قابل‌به‌روزرسانی از ترجیحات و ویژگی‌های رفتاری کاربر، بدون برچسب‌زنی قطعی.

## ابعاد پیشنهادی
- discipline
- planning_preference
- procrastination
- competition
- reward_sensitivity
- stress_tolerance
- routine_preference
- novelty_preference
- self_criticism
- goal_orientation

همه امتیازها در بازه 0..1 هستند و باید همراه confidence ذخیره شوند.

## ساختار مفهومی
```python
class UserModel:
    personality = {}
    preferences = {}
    habits = {}
    behavior = {}
    goals = {}
    current_state = {}
    predictions = {}
    confidence = {}
```

## قواعد
- یک پاسخ منفرد نباید ویژگی را قطعی کند.
- رفتار واقعی می‌تواند باور قبلی را اصلاح کند.
- self-report و observed behavior جدا نگه داشته شوند.
- مدل باید قابل توضیح باشد: برای هر نتیجه، evidence و confidence ثبت شود.
