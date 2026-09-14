# Use Caseهای یکپارچه — نسخه ۱

## UC-01 هدف موضوعی → تست → تحلیل
Goal → Candidate Task (با parity پیشنهادی) → User Placement → Session (Range + Parity) → Questions → Answers → Correction → Attempts → Analytics → Review → Goal Progress → Student State → Reward → Replanning

## UC-02 Timed/Untimed
Timed محدودیت دارد.  
Untimed محدودیت ندارد.  
هر دو actual duration را در صورت امکان ذخیره می‌کنند.

## UC-03 Range + زوج/فرد
کاربر range و parity مشخص می‌کند.  
سیستم فقط سؤال‌های مطابق را انتخاب می‌کند.  
آخرین parity ذخیره می‌شود و روز بعد طرف مقابل پیشنهاد می‌شود.  
اگر تعداد کافی نباشد، پیام واضح داده می‌شود.

## UC-04 Class → Homework → Planner
Class Session → Homework → Task → Capacity → Placement → Completion → Student State

## UC-05 Exam → Weakness
Exam → Question Results → Topic Signals → Student State → Recommendation

## UC-06 Missed Task → Catch-up
Unfinished → Recovery Pool → Priority → Thursday/Friday → User Placement

## UC-07 School Override
کاربر «امروز مدرسه نمی‌روم» را ثبت می‌کند.  
ظرفیت آن روز افزایش می‌یابد.  
برنامه فشرده‌تر چیده می‌شود.

## UC-08 جمعه برنامه‌ریزی
هر جمعه برنامه هفته بعد تنظیم می‌شود.  
تغییرات وسط هفته تا جمعه بعدی معتبر است.

## UC-09 Reward
پس از تکمیل تست یا Task، امتیاز و streak به‌روز می‌شود و در صورت رسیدن به شرط، نشان اهدا می‌شود.
