# Current State Engine — V2.1

## هدف
تخمین وضعیت فعلی کاربر برای برنامه‌ریزی همان روز/هفته.

## Stateهای پیشنهادی
- energy
- focus
- motivation
- stress
- fatigue
- readiness

همه 0..1 و همراه confidence.

## ورودی
- خواب
- self-report
- رفتار اخیر
- completion اخیر
- مدت جلسات
- شکست/موفقیت اخیر
- تعهدات هفته
- روند چند روز گذشته

## اصل
State لحظه‌ای با Personality یکی نیست.

مثال:
```text
personality.procrastination = 0.70
current_state.energy = 0.35
```
این دو مفهوم مستقل‌اند.

## خروجی
State Engine فقط توصیه را تغذیه می‌کند؛ نباید مستقلاً Task بسازد.
