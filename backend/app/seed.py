"""Seed اولیه SS459 — سه کتاب پایه یازدهم ریاضی + نشان‌ها + تنظیمات.

ساختار کتاب‌ها دقیقاً طبق 01_VISION_SCOPE_V1.md:
- شیمی ۲ — مبتکران: فصل → عنوان → زیرعنوان اختیاری؛ Checkup چند عنوان؛
  دو آزمون جامع در پایان هر فصل؛ سوالات کنکور ۱۴۰۴ در پایان کتاب.
- حسابان ۱ — نشر الگو: فصل → درس → بخش؛ هر بخش Level 1/2/3؛
  «سوالات کنکور سراسری» در پایان هر درس.
- فیزیک ۲ — خیلی سبز: فصل → بخش → زیربخش.
"""

from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.jalali import fa_num
from app.models import (Badge, Book, BookNode, Question, QuestionTopicMap, Subject, TestSet,
                        User, UserBookActivation)

RNG = random.Random(459)


def _mk_node(db, book_id, parent_id, node_type, title, code, order):
    n = BookNode(book_id=book_id, parent_id=parent_id, node_type=node_type, title=title,
                 code=code, order_index=order)
    db.add(n)
    db.flush()
    return n


def _mk_test_set(db, book_id, node_id, title, test_type, n_questions, prefix, difficulty=None,
                 topic_nodes=None):
    """ساخت test set + سوالات + topic map (چند-موضوعی مجاز است)."""
    ts = TestSet(book_id=book_id, node_id=node_id, title=title, test_type=test_type)
    db.add(ts)
    db.flush()
    for i in range(1, n_questions + 1):
        q = Question(
            book_id=book_id,
            stable_key=f"{prefix}-{i:04d}",
            test_set_id=ts.id,
            sequence_no=i,
            difficulty_level=difficulty,
            answer_key=str(RNG.randint(1, 4)),
        )
        db.add(q)
        db.flush()
        nodes = topic_nodes if topic_nodes else [node_id]
        for tn in nodes:
            db.add(QuestionTopicMap(question_id=q.id, node_id=tn))
    return ts


# ----------------------------- کتابها ---------------------------------------

def seed_chemistry(db: Session, subject_id: int) -> None:
    """شیمی ۲ — مبتکران."""
    book = Book(stable_key="chem2-mobtakeran", title="شیمی ۲", publisher="مبتکران",
                subject_id=subject_id)
    db.add(book)
    db.flush()
    chapters = [
        ("کیهان؛ زادگاه الفبای هستی", [
            "تاریخچهٔ مدل اتمی",
            "آرایش الکترونی و طیف‌ها",
            "طبقه‌بندی دوره‌ای عناصر",
        ]),
        ("ردپای گازها در زندگی", [
            "مفهوم مول و جرم مولی",
            "قانون‌های گازها",
            "مخلوط گازها و فشار جزئی",
        ]),
        ("آب؛ آهنگ زندگی", [
            "آب و حلالیت",
            "آب‌های طبیعی و رقت",
            "غلظت محلول‌ها",
        ]),
    ]
    ci = 0
    for ch_title, titles in chapters:
        ci += 1
        ch = _mk_node(db, book.id, None, "chapter", f"فصل {fa_num(ci)}: {ch_title}", f"CH{ci}", ci)
        title_nodes = []
        ti = 0
        for t in titles:
            ti += 1
            tn = _mk_node(db, book.id, ch.id, "title", t, f"CH{ci}-T{ti}", ti)
            title_nodes.append(tn)
            _mk_test_set(db, book.id, tn.id, f"تست‌های {t}", "normal", 36,
                         f"chem2-c{ci}-t{ti}")
        # Checkup — ممکن است چند عنوان را پوشش دهد (چند-موضوعی)
        _mk_test_set(db, book.id, ch.id, f"Checkup فصل {fa_num(ci)}", "checkup", 24,
                     f"chem2-c{ci}-ck", topic_nodes=[n.id for n in title_nodes])
        # دو آزمون جامع در پایان هر فصل
        for x in (1, 2):
            _mk_test_set(db, book.id, ch.id, f"آزمون جامع {fa_num(x)} فصل {fa_num(ci)}", "chapter_exam", 30,
                         f"chem2-c{ci}-ex{x}", topic_nodes=[n.id for n in title_nodes])
    # سوالات کنکور ۱۴۰۴ در پایان کتاب (node در سطح کتاب)
    konkur_node = _mk_node(db, book.id, None, "custom", "سوالات کنکور ۱۴۰۴", "KONKUR", 99)
    _mk_test_set(db, book.id, konkur_node.id, "سوالات کنکور ۱۴۰۴", "concours", 60,
                 "chem2-konkur1404")


def seed_calculus(db: Session, subject_id: int) -> None:
    """حسابان ۱ — نشر الگو."""
    book = Book(stable_key="calc1-algho", title="حسابان ۱", publisher="نشر الگو",
                subject_id=subject_id)
    db.add(book)
    db.flush()
    chapters = [
        ("هندسهٔ تحلیلی و جبر", [
            ("فاصله و میان‌نقطه", ["مختصات و فاصله", "تقسیم پاره‌خط"]),
            ("معادلهٔ خط", ["شیب و معادلهٔ خط", "موازی و عمود", "فاصلهٔ نقطه تا خط"]),
            ("معادلهٔ دایره", ["دایره", "موقعیت نسبی خط و دایره"]),
        ]),
        ("توابع", [
            ("مفهوم تابع", ["تعریف تابع", "دامنه و برد"]),
            ("خانوادهٔ توابع", ["تابع درجه دوم", "تابع قدر مطلق", "ریشه و علامت"]),
            ("ترکیب و وارون", ["ترکیب توابع", "وارون"]),
        ]),
        ("مثلثات", [
            ("تناوب و زاویه", ["رادیان", "تناوب"]),
            ("روابط مثلثاتی", ["روابط بنیادی و جمع زاویه‌ها"]),
            ("معادلات مثلثاتی", ["حل معادله مثلثاتی"]),
        ]),
    ]
    ci = 0
    for ch_title, lessons in chapters:
        ci += 1
        ch = _mk_node(db, book.id, None, "chapter", f"فصل {fa_num(ci)}: {ch_title}", f"CH{ci}", ci)
        li = 0
        for lesson_title, sections in lessons:
            li += 1
            lesson = _mk_node(db, book.id, ch.id, "lesson", lesson_title, f"CH{ci}-L{li}", li)
            si = 0
            for sec_title in sections:
                si += 1
                sn = _mk_node(db, book.id, lesson.id, "section", sec_title,
                              f"CH{ci}-L{li}-S{si}", si)
                # هر بخش: Level 1 / 2 / 3
                for lvl, nq in ((1, 24), (2, 20), (3, 16)):
                    _mk_test_set(db, book.id, sn.id, f"Level {lvl}", "normal", nq,
                                 f"calc1-c{ci}-l{li}-s{si}-lv{lvl}", difficulty=lvl)
            # «سوالات کنکور سراسری» در پایان هر درس
            _mk_test_set(db, book.id, lesson.id, "سوالات کنکور سراسری", "concours", 20,
                         f"calc1-c{ci}-l{li}-konkur")


def seed_physics(db: Session, subject_id: int) -> None:
    """فیزیک ۲ — خیلی سبز."""
    book = Book(stable_key="phys2-khalilsabz", title="فیزیک ۲", publisher="خیلی سبز",
                subject_id=subject_id)
    db.add(book)
    db.flush()
    chapters = [
        ("فیزیک و اندازه‌گیری", [
            ("فیزیک و علم", ["کمی‌سازی و برآورد", "دقت و خطا"]),
            ("اندازه‌گیری و یکاها", ["یکاها", "کمیت‌های پایه و فرعی"]),
        ]),
        ("کار و انرژی", [
            ("کار و توان", ["کار", "توان"]),
            ("انرژی و پایستگی", ["انرژی جنبشی", "انرژی پتانسیل", "پایستگی انرژی"]),
        ]),
        ("دینامیک و حرکت دایره‌ای", [
            ("دینامیک", ["قانون‌های نیوتن", "اصطکاک"]),
            ("حرکت دایره‌ای", ["حرکت دایره‌ای یکنواخت"]),
        ]),
        ("ویژگی‌های فیزیکی مواد", [
            ("چگالی و فشار", ["چگالی", "فشار"]),
            ("فشار در سیال ساکن", ["اصل پاسکال", "اصل ارشمیدس"]),
        ]),
        ("نیروی برهم‌کنش الکتریکی", [
            ("بار الکتریکی", ["بار و رساناها"]),
            ("قانون کولن", ["قانون کولن", "میدان الکتریکی"]),
        ]),
    ]
    ci = 0
    for ch_title, sections in chapters:
        ci += 1
        ch = _mk_node(db, book.id, None, "chapter", f"فصل {fa_num(ci)}: {ch_title}", f"CH{ci}", ci)
        si = 0
        for sec_title, subs in sections:
            si += 1
            sn = _mk_node(db, book.id, ch.id, "section", sec_title, f"CH{ci}-S{si}", si)
            bi = 0
            for sub in subs:
                bi += 1
                ssn = _mk_node(db, book.id, sn.id, "subsection", sub,
                               f"CH{ci}-S{si}-SS{bi}", bi)
                _mk_test_set(db, book.id, ssn.id, f"تست‌های {sub}", "normal", 32,
                             f"phys2-c{ci}-s{si}-ss{bi}")


BADGES = [
    ("first_task", "اولین قدم", "اولین Task را تکمیل کردی", "tasks_completed", 1),
    ("first_test", "اولین تست", "اولین جلسهٔ تست را تمام کردی", "tests_completed", 1),
    ("first_import", "حافظهٔ گذشته", "اولین تست قبلی را وارد کردی", "imports", 1),
    ("streak_3", "سه‌روزه", "۳ روز پیاپی فعالیت", "streak", 3),
    ("streak_7", "یک هفتهٔ کامل", "۷ روز پیاپی فعالیت", "streak", 7),
    ("streak_14", "دو هفتهٔ آتشین", "۱۴ روز پیاپی فعالیت", "streak", 14),
    ("streak_30", "یک ماه پایدار", "۳۰ روز پیاپی فعالیت", "streak", 30),
    ("accuracy_80", "تیزبین", "دقت ۸۰٪ با حداقل ۵۰ تلاش", "accuracy", 80),
    ("volume_500", "نیم‌هزار", "۵۰۰ تست زده‌ای", "volume", 500),
    ("volume_1000", "هزارتایی", "۱۰۰۰ تست زده‌ای", "volume", 1000),
    ("coins_100", "سکه‌انداز", "۱۰۰ سکه جمع کردی", "coins", 100),
    ("coins_500", "ثروتمند مطالعه", "۵۰۰ سکه جمع کردی", "coins", 500),
    ("review_50", "جبران‌کننده", "۵۰ مرور موفق", "reviews_resolved", 50),
    ("questionnaire_done", "شناخته‌شده", "پرسشنامهٔ شناخت را کامل کردی", "questionnaire", 1),
    ("week_full", "هفتهٔ بی‌نقص", "همهٔ Taskهای یک هفته را تکمیل کردی", "week_completed", 1),
]


def seed_all(db: Session) -> None:
    if db.query(User).count() > 0:
        return

    # کاربر تک‌نفره
    user = User(username="me", display_name="دانش‌آموز SS459", grade="11", track="mathematics")
    db.add(user)
    db.flush()

    # درس‌ها
    subjects = {}
    for name in ("حسابان", "شیمی", "فیزیک"):
        s = Subject(name=name)
        db.add(s)
        db.flush()
        subjects[name] = s

    seed_chemistry(db, subjects["شیمی"].id)
    seed_calculus(db, subjects["حسابان"].id)
    seed_physics(db, subjects["فیزیک"].id)
    db.flush()

    # فعال‌سازی همهٔ کتاب‌ها
    for b in db.query(Book).all():
        db.add(UserBookActivation(user_id=user.id, book_id=b.id, active=True))

    # نشان‌ها
    for code, title, desc, cond, val in BADGES:
        db.add(Badge(code=code, title=title, description=desc,
                     condition_type=cond, condition_value=val))

    # تنظیمات پیش‌فرض V2
    user.settings_json = {
        "auto_time_adjust": True,       # کاهش تدریجی time limit (قابل خاموش کردن)
        "season_override": None,        # school_term | summer | None
        "planning_style": "count",      # تعداد کار/وعده، نه ساعت‌بندی خشک
        "onboarding_done": False,
    }
    db.commit()
