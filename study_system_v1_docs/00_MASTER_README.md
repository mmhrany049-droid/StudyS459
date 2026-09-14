# مستند مادر — سیستم مدیریت و تحلیل مطالعه (نسخه ۱)

## هدف نسخه ۱
این پروژه یک Todo App نیست.  
یک سیستم یکپارچه برای مدیریت و اندازه‌گیری فرایند یادگیری شخصی است.

چرخه اصلی:
**برنامه‌ریزی (جمعه) → اجرا → ثبت شواهد → تصحیح → تحلیل → تشخیص وضعیت → مرور/جبران → برنامه‌ریزی مجدد**

## محدوده نسخه ۱ (MVP)
- فقط یک کاربر (خودت)
- سه کتاب اصلی پایه یازدهم ریاضی
- موتور تست با انتخاب Range + زوج/فرد
- تحلیل پایه (Coverage + Accuracy + Volume)
- اهداف هفتگی و برنامه‌ریز روزانه
- ظرفیت بر اساس برنامه مدرسه ایرانی
- سیستم جایزه ساده (امتیاز + streak + نشان)
- بدون Social و گروه
- Telegram فقط به عنوان افزونه اختیاری (برنامه بدون آن کامل کار می‌کند)

## سؤال‌هایی که سیستم باید همیشه بتواند پاسخ دهد
1. کاربر چه منابعی دارد؟
2. در هر منبع کجاست؟
3. چه مقدار کار انجام شده؟
4. کیفیت انجام کار چقدر بوده؟
5. کدام موضوع‌ها ضعیف‌اند؟
6. امروز با توجه به ظرفیت واقعی چه کاری مناسب است؟
7. چرا این کار پیشنهاد شده؟
8. بعد از انجام آن، وضعیت کاربر چه تغییری کرده؟

## اسناد نسخه ۱
00 Master README  
01 Vision & Scope V1  
02 Domain Requirements V1  
03 System Relationships  
04 Database Spec V1  
05 Book System  
06 Test Engine (Range + Odd/Even)  
07 Analytics V1  
08 Planning & Goals (Friday Planning)  
09 Academic & School  
10 Reward System  
11 UI/UX V1  
12 Technical Architecture  
13 Business Rules & Edge Cases  
14 API Contract V1  
15 Roadmap V1  
16 Coding Agent Prompts V1  
17 Acceptance Tests V1  
18 Open Decisions  
19 Integrated Use Cases V1  
20 Implementation Checklist V1  
PROJECT_MANIFEST.json

## قانون طلایی برای عامل کدنویس
- هیچ زیرسیستم نباید منطق متناقض خودش را داشته باشد.
- Planner، Analytics و Test Engine باید از domain/serviceهای مشترک استفاده کنند.
- Telegram فقط مصرف‌کننده سرویس‌های اصلی است و نباید منطق جداگانه داشته باشد.
- اگر چیزی در Open Decisions است، حدس نزن.
- تمرکز فقط روی نسخه ۱ باشد. ویژگی‌های نسخه ۲ را پیاده نکن.
