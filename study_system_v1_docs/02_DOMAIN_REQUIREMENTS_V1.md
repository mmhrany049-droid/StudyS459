# نیازمندی‌های دامنه — نسخه ۱

## User (تک‌کاربره)
اطلاعات تحصیلی، کتاب‌های فعال، مدرسه، کلاس‌ها، تکالیف، امتحانات، اهداف، Taskها، تاریخچه، امتیاز، streak و تنظیمات.

## Book
دارای stable_key.
فعال/غیرفعال‌کردن کتاب فقط روی استفاده‌های جدید اثر دارد؛ history حذف نمی‌شود.

## Book Node
ساختار درختی generic است و می‌تواند chapter، lesson، title، section، subsection، leaf یا نوع سفارشی داشته باشد.

## Question
دارای:
- stable_key
- book
- test set
- sequence_no
- answer key
- difficulty اختیاری
- mapping به یک یا چند topic (node)

## Test Set
انواع قابل پشتیبانی:
normal, checkup, chapter_exam, comprehensive, concours, mock, custom

## Weekly Goal
دو نوع مستقل:
- تعداد تست
- موضوع

می‌تواند فقط یکی یا هر دو را داشته باشد.
وقتی هر دو وجود دارند، هدف موضوعی اولویت دارد و هدف تعداد حجم کلی را کنترل می‌کند.

## Task
از goal، homework، exam، review یا manual ساخته می‌شود و source reference دارد.

## Planner (نسخه ۱)
- برنامه‌ریزی اصلی هر جمعه برای یک هفته کامل انجام می‌شود.
- امکان تنظیم و تغییر برنامه در وسط هفته وجود دارد، اما افق برنامه‌ریزی تا جمعه بعدی است.
- شنبه تا چهارشنبه: برنامه عادی (با توجه به ظرفیت مدرسه)
- پنج‌شنبه و جمعه: catch-up یا مطالعه فشرده‌تر
- سیستم پیشنهاد می‌دهد؛ کاربر placement نهایی را کنترل می‌کند.

## Test
هر Task تست می‌تواند یک Test Session ایجاد کند.

### زمان
Timed:
- محدودیت زمانی دارد.
- countdown دارد.

Untimed:
- هیچ محدودیت زمانی ندارد.
- countdown ندارد.
- زمان واقعی صرف‌شده در صورت ثبت، فقط داده تحلیلی است.

### انتخاب سؤال (قانون اصلی نسخه ۱)
- کاربر range مشخص می‌کند (مثلاً از sequence_no = ۲۱ تا ۴۱)
- سپس parity انتخاب می‌کند: فقط فرد یا فقط زوج یا همه
- سیستم آخرین parity استفاده‌شده برای آن node را به خاطر می‌سپارد و روز بعد طرف مقابل را پیشنهاد می‌دهد.
- اگر تعداد سؤال کافی در آن parity نباشد، session ساخته نمی‌شود و دلیل واضح نمایش داده می‌شود.

## Result
سه وضعیت مستقل:
correct / wrong / unanswered

## History
هیچ attempt قبلی overwrite نشود (append-only).

## Academic
School + External Class + Taught Lesson + Homework + Exam.
تدریس‌شده هرگز خودکار learned محسوب نمی‌شود.

## Reward
امتیاز، streak و نشان‌های ساده.

## Telegram
افزونه اختیاری. برنامه بدون آن کامل کار می‌کند.
