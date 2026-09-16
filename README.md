# SS459 — Study System 4-5-9
سیستم مدیریت و تحلیل مطالعه — نسخه ۲.۱

پیاده‌سازی نسخه ۲.۱ بر اساس بسته مستندات `study_system_v2_docs` (V2) و `study_system_v2_1_docs` (V2.1)
روی هسته نسخه ۱ (`study_system_v1_docs`).

## Stack
- Backend: Python + FastAPI + Pydantic + SQLAlchemy + SQLite
- Frontend: React + Vite + TypeScript + Tailwind (RTL, فارسی، تقویم شمسی، فونت وزیرمتن)
- تک‌کاربره، timezone: Asia/Tehran، هفته شنبه تا جمعه

## اجرا

```bash
# بک‌اند
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py            # سرور روی :8000 (API + رابط کاربری)

# فرانت‌اند (توسعه)
cd frontend
npm install
npm run dev                        # Vite روی :5173 با proxy به :8000
npm run build                      # خروجی در frontend/dist (توسط FastAPI سرو می‌شود)
```

دیتابیس و seed اولیه (سه کتاب، کلاس‌های پیش‌فرض، نشان‌ها) به‌صورت خودکار ساخته می‌شود:
`backend/data/study.db`

## محدوده پیاده‌سازی

### هسته V1 (حفظ‌شده)
- Range + parity (odd/even/any) با پیام خطای دقیق «فقط X سوال با این شرایط وجود دارد.»
- correct / wrong / unanswered مستقل؛ history کاملاً append-only؛ finish ایدمپوتنت
- Coverage جدا از Accuracy جدا از Volume
- اهداف هفتگی (تعداد + موضوع) و Planner افق جمعه
- ظرفیت روزانه بر اساس برنامه مدرسه ایرانی + override «امروز مدرسه نمی‌روم»

### V2
- تقویم شمسی + هفته شنبه‌محور + فصل‌ها (school_term / summer)
- کلاس‌های تقویتی پیش‌فرض (حسابان، شیمی، فیزیک) + بونوس +۱۵ در روز کلاس
- Past Test Import (بدون سکه)
- actual duration برای Untimed + میانگین زمان per node
- کاهش تدریجی time limit در Timed (قابل خاموش کردن)
- مرور خوشه‌ای + تصادفی (سقف ۲۵، حداقل خوشه ۸، critical wrong≥2)
- سکه + بیدار شدن + streak سخت‌گیرانه
- Habit advice فقط بعد از ۳۰ روز داده
- وعده ۶۰ تا ۱۲۰ دقیقه؛ «۲ وعده / ۴ کار» به‌جای ساعت‌بندی خشک

### V2.1 — لایه Behavioral Intelligence
- User Profile / Personality (۱۰ بعد، 0..1 + confidence + evidence)
- پرسشنامه تطبیقی (~۴۰ سؤال، انتخاب سؤال بعدی بر اساس uncertainty)
- مصاحبه برنامه‌ریزی ابتدای هر هفته (۶ گروه سؤال، خروجی ورودی Planner)
- Behavior Engine (رویدادهای append-only + features قابل بازمحاسبه)
- State Engine (energy/focus/motivation/stress/fatigue/readiness + confidence)
- Capacity Estimator از داده واقعی (محافظه‌کارانه قبل از ۳۰ روز)
- تشخیص الگوی اهمال‌کاری + پیشنهاد split / entry point کوچک / شروع با ۵ تست
- Planning Engine با وزن‌های ثابت V2 + لایه رفتاری + خروجی توضیح‌پذیر
- Manual Override کامل (ایجاد/حذف/جابه‌جایی/split/merge/تغییر تعداد/اولویت/زمان)
- Planner هرگز Task دستی را بدون اجازه overwrite نمی‌کند
- حلقه Plan → Act → Observe → Evaluate → Update
- همه پیش‌بینی‌ها دارای confidence + evidence_count

خارج از محدوده (طبق مستندات): شبکه عصبی سنگین، Spaced Repetition کامل، Social،
پیش‌بینی بلندمدت کنکور، Telegram (اختیاری و غیرضروری — پیاده نشده).
