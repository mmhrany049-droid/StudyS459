# APIهای جدید / گسترش نسخه ۲

## Import
POST /test-sessions/import  
GET /test-sessions?imported=true

## زمان
PATCH /test-sessions/{id}/duration  { "actual_duration_minutes": 45 }

## بیدار شدن
POST /rewards/wake-up  
GET /rewards/summary  (شامل سکه و streak)

## کلاس پیش‌فرض
POST /schedules/seed-defaults  
GET /schedules

## عادت
GET /habits/summary  
→ میانگین کار روز مدرسه/آزاد، تعداد روز فعال، آیا از آستانه ۳۰ روز گذشته

## تاریخ
API می‌تواند میلادی بماند؛ UI تبدیل شمسی می‌کند. در صورت نیاز فیلد display_jalali در responseهای روز/هفته.
