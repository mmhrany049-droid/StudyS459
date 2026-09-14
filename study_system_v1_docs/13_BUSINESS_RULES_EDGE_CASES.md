# قوانین کسب‌وکار و Edge Cases — نسخه ۱

## Book
- stable_key unique
- no tree cycle
- parent same book
- valid order
- sequence_no یکتا و صعودی

## Question
- stable_key unique per book
- answer key required for automatic correction
- multi-topic allowed

## Session
- no duplicate question inside one session
- finish idempotent
- finalized session immutable unless correction flow
- اگر تعداد سؤال در range + parity کافی نباشد → session ساخته نشود

## Untimed
timed=false و time_limit=null.  
وجود response time هرگز timed را true نمی‌کند.

## Timed
timed=true و time_limit>0.

## Result invariant
correct + wrong + unanswered = total

## Missing Answer Key
سیستم نباید وانمود کند auto-correction انجام شده.  
Session می‌تواند pending correction باشد.

## Empty / Insufficient Pool
اگر تعداد سؤال کافی نیست:
- session را به شکل ناقص ایجاد نکن.
- دلیل را واضح بگو (مثلاً «فقط ۱۲ سؤال فرد در این بازه وجود دارد»).
- امکان تغییر معیار/تعداد/parity بده.

## Disabled Book
history حفظ شود؛ فقط در پیشنهادهای جدید استفاده نشود.

## Over Capacity
هشدار بده؛ task را خودکار حذف نکن.

## School Override
اگر روز به عنوان «مدرسه نمی‌روم» علامت خورده باشد، ظرفیت آن روز افزایش می‌یابد.

## Duplicate Import
شناسه/Hash/Idempotency key برای تشخیص import تکراری.

## Goal Overlap
یک task ممکن است چند goal را پوشش دهد؛ counting نباید double-count شود.

## Timezone
زمان user-facing بر اساس timezone کاربر (Asia/Tehran).

## Concurrency
دو submit همزمان نباید duplicate attempt بسازد.

## Planning Horizon
برنامه از جمعه تا جمعه بعدی معتبر است.  
تغییرات وسط هفته فقط تا جمعه اثر دارد.
