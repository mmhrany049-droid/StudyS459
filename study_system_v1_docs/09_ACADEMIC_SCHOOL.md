# مدرسه، کلاس، تکلیف و امتحان — نسخه ۱

## School Schedule (ایران)
- شنبه تا چهارشنبه: روز مدرسه
- پنج‌شنبه و جمعه: روز آزاد
- فصل پاییز، زمستان، بهار: حالت مدرسه فعال
- تابستان: حالت تعطیلی (ظرفیت کامل هر روز)

روز، شروع، پایان، درس، زنگ اختیاری.

## School Day Override
کاربر می‌تواند برای یک تاریخ مشخص بگوید:
«امروز مدرسه نمی‌روم» یا «فلان روز هفته مدرسه نمی‌روم».

اثر:
- ظرفیت آن روز به حالت روز آزاد تغییر می‌کند.
- برنامه فشرده‌تر و سنگین‌تر چیده می‌شود.
- قابل برگشت است.

## External Class
روز، ساعت، درس، استاد/مؤسسه اختیاری، تکرار، topic اختیاری.

## Class Session
date, attendance, notes, subject.

## Taught Lesson
date, subject, node, duration, notes.

تدریس‌شدن باعث افزایش خودکار mastery یا coverage نمی‌شود.

## Homework
title, source, subject, node, due_at, estimate, priority, status.

Homework می‌تواند Task تولید کند.

## Exam
metadata + questions + answer key + user answers + result + topic mapping.

## Exam Analytics
آمار امتحان مستقل باقی می‌ماند.  
نتایج امتحان می‌توانند سیگنال Student State و ضعف باشند.

## Import
JSON ساده در نسخه ۱.  
duplicate-safe.
