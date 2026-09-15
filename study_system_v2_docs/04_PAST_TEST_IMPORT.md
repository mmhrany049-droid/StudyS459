# وارد کردن تست‌های قبلی

## هدف
کاربر قبل از اپ تست زده؛ نباید از صفر شروع کند.

## جریان
1. ساخت «جلسه واردشده» (imported session)
2. انتخاب کتاب / node / test_set و در صورت نیاز range و parity
3. برای هر سوال: correct | wrong | unanswered (+ پاسخ اختیاری)
4. تاریخ جلسه (پیش‌فرض امروز، قابل تغییر — نمایش شمسی)
5. تأیید نهایی

## اثر
- `test_session` با `is_imported = true` و `status = completed`
- `question_attempts` append-only
- غلط و نزده → `review_queue`
- Analytics فوراً به‌روز
- **سکه تعلق نمی‌گیرد**

## محدودیت‌ها
- overwrite ممنوع
- امکان چند import پشت سر هم
- در آمار Volume/Coverage/Accuracy لحاظ می‌شود
