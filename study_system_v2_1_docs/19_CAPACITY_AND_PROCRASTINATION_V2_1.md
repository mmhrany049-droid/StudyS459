# ظرفیت و الگوهای اهمال‌کاری — V2.1

## Capacity Estimator
ظرفیت واقعی از عملکرد گذشته برآورد شود:
- completed tasks/day
- school vs free days
- average session duration
- weekly goal completion
- recent trend

قبل از داشتن 30 روز داده، نتیجه‌گیری ظرفیت باید محافظه‌کارانه باشد.

## نمونه
اگر برنامه‌های 4 تا 5 کاری مرتباً به 2 کار ختم شده‌اند، سیستم باید پیشنهاد کاهش بار بدهد، نه سرزنش کاربر.

## Procrastination Pattern Detection
الگوهای ممکن:
```text
Hard Task
  ↓
Delay
  ↓
Late Start
  ↓
Stress
  ↓
Lower Completion
```

سیستم می‌تواند با داده کافی:
- Task سخت را split کند.
- entry point کوچک بسازد.
- ترتیب Taskها را تغییر دهد.
- پیشنهاد شروع با 5 تست بدهد.

هیچ تشخیص پزشکی/روان‌شناختی صادر نشود.
