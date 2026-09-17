# ماتریس Audit (V3 → V3.1)

ستون اقدام را هنگام بررسی کد واقعی شاخه V3 پر کنید. وضعیت اولیه بر اساس ساختار ریپو و کامیت‌هاست (تخمینی تا verify).

| قابلیت | انتظار از نسخه‌های قبل | در V3 (ظاهری) | الزام V3.1 |
|--------|------------------------|---------------|-----------|
| Range + parity تست | V1 | testing/selection | حفظ + باگ‌فیکس |
| بانک تست per مبحث + پاسخ‌نامه | V2.2 | QuestionBank, ResponseSheet | کامل، لیست چهارگزینه‌ای سریع |
| Import گذشته کتاب + نزده | V2.2 | ImportPast | حفظ؛ UX واضح |
| Taught تیک + cascade فصل | V2.2 | بررسی کد | اگر نیست اضافه؛ اگر هست تست cascade |
| Daily/Weekly check-in | V2.2/V3 | کامیت recovery | هدف‌دار اتصال به capacity/planner |
| پرسشنامه شخصیت چندپهلو | V2.1/V2.2 | ؟ | تقویت؛ delta کوچک؛ سناریو |
| آزمون آزمایشی چنددرسه | V2.2 | Exams + topic mark | Exam Center کامل Past/Upcoming |
| آمادگی امتحان | V2.2/V3 | readiness card | برنامه چندروزه + پیشنهاد تست |
| فایل PDF/عکس امتحان | V2.2/V3 | exam files | حفظ |
| Jalali UI | V2/V3 | اعلام شده | فقط شمسی؛ سال ۱۴۰۵–۱۴۰۸ |
| Curriculum ۱۰–۱۲ | نیاز V3.1 | Curriculum page | درخت کامل؛ plannable فقط با تست |
| Checkup شیمی range | نیاز کاربر | ؟ | مدل Coverage Range اجباری |
| StudyTask چندنوع | نیاز V3.1 | tasks service | مدل type قابل گسترش |
| Telegram | همیشه optional | ؟ | non-blocking اگر هست |

Agent قبل از feature جدید باید این جدول را با نتیجه PASS/FAIL روی کد واقعی به‌روز کند.
