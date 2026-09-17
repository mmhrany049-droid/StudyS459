# سیستم آزمون V3.1 (اولویت خیلی بالا)

## مدل یکپارچه Exam

```
Exam
├── name
├── type: personal | school | mock | checkup | comprehensive
├── date (جلالی در UI)
├── duration_minutes (برنامه / حد)
├── question_count
├── subjects[]
├── topics[]          # با تیک سلسله‌مراتبی
├── source / notes
├── files[]           # pdf/image اختیاری
├── answer_key[]      # sequence → 1..4
└── attempts[]
       ├── at
       ├── duration_spent
       ├── answers
       └── result summary
```

## ارتباط با مباحث
هر Exam می‌تواند چند Subject و چند Topic داشته باشد.
تیک مبحث مثل Taught: تیک فصل ⇒ همه فرزندان برای همان Exam.

## چکاپ شیمی (مدل اجباری)
Checkup ≠ یک Topic تکی.

```
Checkup
├── coverage_range
├── start_after_topic / previous_checkup
├── end_before_topic / this_checkup
└── included_topics[]   # از سگمنت قبلی تا قبل چکاپ فعلی
```
یعنی Test Session با محدوده پوشش چند مبحث.

## Exam Center در محصول
### گذشته
- لیست آزمون‌های برگزارشده
- نتیجه per درس / کل
- ضعف‌ها و follow-up

### آینده
- تاریخ و مباحث
- برنامه آماده‌سازی چندروزه
- پیشنهاد تست آرام از بانک همان مباحث

### Retake
- نوبت جدید؛ تاریخچه overwrite نشود
- فلگ keep_for_retake / use_for_future_prep

## انواع در UI
کاربر هنگام ساخت، type را انتخاب می‌کند؛ فرم فیلدهای مشترک + فیلدهای خاص mock (چند درس) را نشان می‌دهد.
