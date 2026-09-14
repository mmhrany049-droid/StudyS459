# اهداف و برنامه‌ریزی — نسخه ۱

## قانون اصلی برنامه‌ریزی
- برنامه‌ریزی اصلی هر **جمعه** برای یک هفته کامل انجام می‌شود.
- افق برنامه‌ریزی از شنبه تا جمعه بعدی است.
- امکان تغییر و تنظیم برنامه در وسط هفته وجود دارد، اما پایه برنامه تا جمعه باقی می‌ماند.

## Goal
دو نوع:
- count (تعداد تست)
- topic (موضوع)

## Candidate Pool
سیستم پیشنهادها را از:
- هدف موضوعی
- هدف تعداد
- ضعف‌ها
- review
- homework
- exam
- overdue
- آخرین parity
تولید می‌کند.

## Priority
سیگنال‌های قابل وزن‌دهی:
- deadline
- topic goal
- review criticality
- exam proximity
- homework
- count goal
- weakness
- capacity
- parity مناسب

## Recommendation Reason
هر پیشنهاد علت داشته باشد، مانند:
«هدف موضوعی هفته + ضعف اخیر + parity مخالف روز قبل + ظرفیت مناسب»

## Capacity
- زمان‌های مدرسه و کلاس ظرفیت را کاهش می‌دهند.
- اگر روز به عنوان «مدرسه نمی‌روم» علامت خورده باشد، ظرفیت به حالت روز آزاد تغییر می‌کند.
- اگر workload > capacity:
  - هشدار
  - breakdown
  - امکان جابه‌جایی
  - بدون حذف خودکار

## Placement
Candidate Task با Daily Placement متفاوت است.  
کاربر تصمیم نهایی placement را می‌گیرد.

## روزها
- شنبه تا چهارشنبه: normal planning (با ظرفیت مدرسه)
- پنج‌شنبه و جمعه: catch-up یا مطالعه فشرده‌تر

## Catch-up priority
1. overdue/deadline
2. homework
3. goal-critical
4. review-critical
5. سایر unfinished

## Replanning
پس از completion:
- goal update
- analytics update
- review update
- state update
- reward update
- candidate recalculation

## Task Status
planned / in_progress / completed / overdue / cancelled
