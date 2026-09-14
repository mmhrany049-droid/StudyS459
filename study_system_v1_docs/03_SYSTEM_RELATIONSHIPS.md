# روابط عمیق سیستم‌ها — نسخه ۱

## Content Graph
Book → Nodes → Test Sets → Questions

## Evidence
Test Session → Attempts  
Exam → Exam Question Results  
Taught Lesson  
Homework Completion

## Analytics
Evidence خام → Volume + Coverage + Accuracy + Time Signals + Topic Signals

## Student State
Student State از:
- Analytics
- Review Queue
- Goals
- Homework
- Exams
- Schedule
- Unfinished Tasks
- Reward (امتیاز و streak)
تغذیه می‌شود.

## Planning
Student State + Goals + Schedule + Deadlines + Capacity
→ Candidate Tasks
→ Priority
→ Recommendation Reason
→ User Placement
→ Execution

## حلقه بازخورد
Execution → Evidence → Analytics → Student State → Recommendation

## زنجیره مهم (با قانون زوج/فرد)
Weekly Goal  
→ Candidate Test Task (با پیشنهاد parity مناسب)  
→ Daily Placement  
→ Test Session (Range + Parity)  
→ Questions  
→ Answers  
→ Correction  
→ Attempts  
→ Progress  
→ Weakness/Review  
→ Student State + Reward  
→ Next Recommendations

## مثال
هدف موضوع X ثبت می‌شود.  
سیستم ضعف X را می‌بیند و آخرین parity را چک می‌کند.  
Task تست X با parity مخالف ساخته می‌شود.  
کاربر آن را برای دوشنبه قرار می‌دهد.  
۲۰ سؤال فرد از ۲۱ تا ۴۱ انتخاب می‌شوند.  
کاربر Untimed را انتخاب می‌کند.  
۱۷ درست، ۲ غلط، ۱ نزده.  
۲۰ attempt ذخیره می‌شود.  
Analytics و Reward به‌روزرسانی می‌شود.  
غلط و نزده برای مرور candidate می‌شوند.  
Goal progress و Student State تغییر می‌کنند.

## ممنوع
- Planner منطق مستقل تست نداشته باشد.
- Telegram (اگر فعال باشد) درصد را جداگانه محاسبه نکند.
- Book importer برای سه کتاب شرط hard-code نداشته باشد.
