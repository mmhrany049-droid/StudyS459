# موتور تست — نسخه ۱ (Range + زوج/فرد)

## Lifecycle
Task → Start Session → Select → Answer → Finish → Correct → Persist → Analyze → Review → Complete Task → Reward

## Selection (قانون اصلی نسخه ۱)

ورودی‌ها:
- book
- node (یا criteria)
- count
- sequence_from (اختیاری)
- sequence_to (اختیاری)
- parity: odd | even | any
- timed mode

قوانین:
1. اگر sequence_from و sequence_to مشخص شده باشد، فقط سؤال‌های داخل این بازه در نظر گرفته می‌شوند.
2. اگر parity = odd → فقط sequence_no فرد
3. اگر parity = even → فقط sequence_no زوج
4. اگر parity = any → همه
5. انتخاب نهایی از pool مجاز به صورت تصادفی انجام می‌شود (بدون تکرار داخل session).
6. اگر تعداد سؤال کافی در pool نباشد:
   - session ساخته نمی‌شود
   - پیام واضح نمایش داده می‌شود
   - امکان تغییر range یا parity یا count داده می‌شود

## مدیریت Parity
- سیستم برای هر node آخرین parity استفاده‌شده را در جدول node_parity_state ذخیره می‌کند.
- هنگام پیشنهاد Task جدید، parity مخالف آخرین را پیشنهاد می‌دهد (اگر کاربر بخواهد).
- کاربر می‌تواند parity را دستی تغییر دهد.

## Timed
timed = true  
time_limit_seconds > 0  
countdown فعال.  
رفتار timeout باید deterministic و تست‌شده باشد.

## Untimed
timed = false  
time_limit_seconds = null  
countdown ندارد.  
timeout ندارد.  
پایان با Finish.  
actual duration می‌تواند ثبت شود اما محدودیت نیست.

## Answers
correct / wrong / unanswered

Unanswered یعنی هنگام پایان پاسخی ثبت نشده؛ wrong نیست.

## Finish
idempotent.  
فرآیند دوباره نباید duplicate attempt بسازد.

## History
هر attempt مستقل است.  
اجرای دوباره سؤال previous attempt را overwrite نمی‌کند.

## Result
- total
- correct
- wrong
- unanswered
- accuracy
- duration
- average response time
- topic breakdown
- difficulty breakdown
- parity استفاده‌شده
- range استفاده‌شده

## Scoring
فرمول نمره منفی و مدل‌های scoring باید configurable باشند؛ در نسخه ۱ تصمیم نهایی گرفته نشده و باید ساده نگه داشته شود (فعلاً فقط correct/wrong/unanswered).
