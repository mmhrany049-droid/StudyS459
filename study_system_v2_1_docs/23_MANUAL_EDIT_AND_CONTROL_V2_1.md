# کنترل دستی برنامه — V2.1

## اصل غیرقابل مذاکره
کاربر مالک برنامه است.

## عملیات مجاز
- create task
- edit task
- delete task
- move task between days
- split task
- merge task
- change quantity
- change priority
- set/unset time
- complete/uncomplete طبق قوانین سیستم
- accept/reject suggestion

## منبع
هر Task یکی از sourceها را داشته باشد:
- manual
- planner
- imported
- recurring

برای تغییرات:
- created_by
- updated_by
- updated_at
- override_reason اختیاری

## جلوگیری از overwrite
Planner نباید Task دارای manual override را خودکار تغییر دهد، مگر کاربر صریحاً «بازسازی برنامه» را تأیید کند.

## UI
در صفحه هفته:
- «پیشنهاد سیستم»
- «ویرایش دستی»
- «بازسازی برنامه»
جدا و واضح باشند.
