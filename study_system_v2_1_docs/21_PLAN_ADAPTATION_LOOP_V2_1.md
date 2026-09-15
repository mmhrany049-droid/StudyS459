# حلقه یادگیری و تطبیق — V2.1

```text
Plan
 ↓
Act
 ↓
Observe
 ↓
Evaluate
 ↓
Update User Model
 ↓
Better Plan
```

## معیارهای ارزیابی
- completion rate
- actual duration
- skipped tasks
- edits
- rescheduling
- test accuracy
- review outcomes

## قواعد
- سیستم از شکست برنامه یاد بگیرد، نه اینکه کاربر را سرزنش کند.
- اگر بار زیاد بود، ظرفیت را کاهش دهد.
- اگر بار مرتباً به‌راحتی کامل شد، افزایش تدریجی پیشنهاد شود.
- تغییر ظرفیت باید gradual باشد.
- manual override نشانه «خطا» نیست.
