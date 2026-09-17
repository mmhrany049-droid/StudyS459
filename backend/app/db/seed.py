"""Idempotent seeding: curriculum from the repository content, V2 default classes,
badges, onboarding question bank and the research registry skeleton.

Nothing here fabricates user data (no fake attempts, exams or results): an empty
installation starts empty and the UI shows guided empty states.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .seed_content import ParsedBook, ParsedNode, load_all

SUBJECTS = [
    {"slug": "calculus", "name": "حسابان", "color": "#6366f1", "order": 1},
    {"slug": "chemistry", "name": "شیمی", "color": "#14b8a6", "order": 2},
    {"slug": "physics", "name": "فیزیک", "color": "#f59e0b", "order": 3},
]

DEFAULT_CLASSES = [
    {"title": "کلاس تقویتی حسابان", "slug": "calculus"},
    {"title": "کلاس تقویتی شیمی", "slug": "chemistry"},
    {"title": "کلاس تقویتی فیزیک", "slug": "physics"},
]

BADGES = [
    ("first_20_tests", "اولین ۲۰ تست", "۲۰ سؤال را پاسخ داده‌ای.", "question_count", 20, "🎯"),
    ("chapter_coverage_80", "پوشش ۸۰٪ فصل", "یک فصل با پوشش حداقل ۸۰٪.", "coverage", 0.8, "🗺️"),
    ("streak_7", "۷ روز پیوسته", "هفت روز متوالی فعالیت.", "streak", 7, "🔥"),
    ("streak_30", "۳۰ روز پیوسته", "سی روز متوالی فعالیت.", "streak", 30, "🏅"),
    ("accuracy_75", "دقت ۷۵٪", "دقت ≥ ۷۵٪ روی یک مبحث با حداقل ۲۰ تلاش.", "accuracy", 0.75, "✅"),
    ("weekly_topic_goal", "هدف هفتگی", "یک هدف موضوعی هفتگی کامل شد.", "weekly_goal", 1, "📅"),
]

# ---------------------------------------------------------------------------
# Adaptive onboarding question bank (multi-facet: every answer nudges 2..4
# dimensions with *small* deltas - V2.2 personality strengthening)
# ---------------------------------------------------------------------------

ONBOARDING = [
    {
        "code": "plan_start_style",
        "group": "سبک برنامه‌ریزی",
        "text": "اگر فردا ۶ ساعت وقت آزاد داشته باشی، کدام حالت طبیعی‌تر است؟",
        "options": [
            {"id": "morning", "label": "از صبح شروع می‌کنم"},
            {"id": "easy_first", "label": "با کار ساده شروع می‌کنم"},
            {"id": "delay", "label": "شروع را عقب می‌اندازم"},
            {"id": "depends", "label": "بستگی به انرژی آن روز دارد"},
        ],
        "effects": {
            "morning": {"discipline": 0.05, "routine_preference": 0.04},
            "easy_first": {"procrastination": 0.03, "novelty_preference": -0.02, "discipline": 0.02},
            "delay": {"procrastination": 0.06, "discipline": -0.03, "self_criticism": 0.02},
            "depends": {"routine_preference": -0.03, "stress_tolerance": 0.02},
        },
    },
    {
        "code": "plan_detail",
        "group": "سبک برنامه‌ریزی",
        "text": "برنامه‌ات را چطور می‌خواهی؟",
        "options": [
            {"id": "exact", "label": "با ساعت دقیق هر کار"},
            {"id": "semi", "label": "فقط تعداد کار در روز"},
            {"id": "flex", "label": "کاملاً انعطاف‌پذیر، خودم تصمیم می‌گیرم"},
        ],
        "effects": {
            "exact": {"planning_preference": 0.07, "routine_preference": 0.04},
            "semi": {"planning_preference": 0.02},
            "flex": {"planning_preference": -0.06, "novelty_preference": 0.04},
        },
    },
    {
        "code": "hard_task_reaction",
        "group": "شروع کار",
        "text": "وقتی یک مبحث سخت جلوی توست، معمولاً چه می‌کنی؟",
        "options": [
            {"id": "dive", "label": "شروع می‌کنم و در راه حل می‌کنم"},
            {"id": "split", "label": "آن را به قطعه‌های کوچک می‌شکنم"},
            {"id": "postpone", "label": "به بعد موکول می‌کنم"},
            {"id": "escape", "label": "سراغ کارهای ساده‌تر می‌روم"},
        ],
        "effects": {
            "dive": {"discipline": 0.05, "stress_tolerance": 0.03},
            "split": {"planning_preference": 0.04, "discipline": 0.03},
            "postpone": {"procrastination": 0.06, "self_criticism": 0.02},
            "escape": {"procrastination": 0.05, "novelty_preference": 0.03, "stress_tolerance": -0.03},
        },
    },
    {
        "code": "error_reaction",
        "group": "واکنش به خطا",
        "text": "بعد از یک تست که چند غلط داری، اولین کارت چیست؟",
        "options": [
            {"id": "review_now", "label": "همان‌جا غلط‌ها را بررسی می‌کنم"},
            {"id": "later", "label": "برای مرور بعدی کنار می‌گذارم"},
            {"id": "ignore", "label": "زیاد نگاه نمی‌کنم، ادامه می‌دهم"},
            {"id": "upset", "label": "روحم می‌ریزد و سخت ادامه می‌دهم"},
        ],
        "effects": {
            "review_now": {"discipline": 0.04, "goal_orientation": 0.03},
            "later": {"planning_preference": 0.03},
            "ignore": {"procrastination": 0.03, "self_criticism": -0.02},
            "upset": {"self_criticism": 0.06, "stress_tolerance": -0.04},
        },
    },
    {
        "code": "reward_reaction",
        "group": "انگیزه و پاداش",
        "text": "چه چیزی بیشتر به تو انرژی می‌دهد؟",
        "options": [
            {"id": "points", "label": "دیدن امتیاز و سکه"},
            {"id": "progress", "label": "دیدن پیشرفت واقعی در درصد/پوشش"},
            {"id": "compare", "label": "مقایسه با دیگران"},
            {"id": "goal", "label": "نزدیک شدن به هدف نهایی"},
        ],
        "effects": {
            "points": {"reward_sensitivity": 0.07, "competition": 0.02},
            "progress": {"goal_orientation": 0.05, "reward_sensitivity": 0.02},
            "compare": {"competition": 0.07, "stress_tolerance": -0.02},
            "goal": {"goal_orientation": 0.06, "discipline": 0.02},
        },
    },
    {
        "code": "exam_pressure",
        "group": "فشار و استرس",
        "text": "هفته آخر قبل امتحان، حالت چطور است؟",
        "options": [
            {"id": "focused", "label": "متمرکزتر می‌شوم"},
            {"id": "anxious", "label": "استرس بالا می‌رود ولی کار می‌کنم"},
            {"id": "blocked", "label": "استرس مانع شروع می‌شود"},
            {"id": "calm", "label": "تقریباً فرقی نمی‌کند"},
        ],
        "effects": {
            "focused": {"stress_tolerance": 0.06, "goal_orientation": 0.03},
            "anxious": {"stress_tolerance": 0.02, "self_criticism": 0.03},
            "blocked": {"stress_tolerance": -0.06, "procrastination": 0.04},
            "calm": {"stress_tolerance": 0.03, "self_criticism": -0.02},
        },
    },
    {
        "code": "sleep_pattern",
        "group": "خواب و بیداری",
        "text": "معمولاً چه ساعتی می‌خوابی و بیدار می‌شوی؟",
        "options": [
            {"id": "early", "label": "زود می‌خوابم، زود بیدار می‌شوم"},
            {"id": "late", "label": "دیر می‌خوابم، دیر بیدار می‌شوم"},
            {"id": "variable", "label": "ثابت نیست"},
            {"id": "little", "label": "کم می‌خوابم"},
        ],
        "effects": {
            "early": {"discipline": 0.05, "routine_preference": 0.05},
            "late": {"routine_preference": -0.02, "discipline": -0.02},
            "variable": {"routine_preference": -0.04, "planning_preference": -0.02},
            "little": {"stress_tolerance": -0.03, "self_criticism": 0.02},
        },
    },
    {
        "code": "subject_focus",
        "group": "هدف",
        "text": "این ماه کدام درس بیشترین اولویت را دارد؟",
        "options": [],
        "effects": {},
        "kind": "subject_focus",
    },
    {
        "code": "goal_target",
        "group": "هدف",
        "text": "بزرگ‌ترین نتیجه‌ای که سه ماه آینده می‌خواهی ببینی چیست؟",
        "kind": "short_text",
        "options": [],
        "effects": {},
    },
    {
        "code": "work_style_flex",
        "group": "انعطاف‌پذیری",
        "text": "اگر برنامه عقب بیفتد، چه می‌کنی؟",
        "options": [
            {"id": "catchup", "label": "جبران می‌کنم"},
            {"id": "replan", "label": "برنامه را بازتنظیم می‌کنم"},
            {"id": "drop", "label": "کارهای کم‌اهمیت را حذف می‌کنم"},
            {"id": "stuck", "label": "معمولاً جا می‌مانم"},
        ],
        "effects": {
            "catchup": {"discipline": 0.04, "stress_tolerance": 0.02},
            "replan": {"planning_preference": 0.05, "novelty_preference": 0.02},
            "drop": {"planning_preference": 0.03, "stress_tolerance": 0.03, "self_criticism": -0.03},
            "stuck": {"procrastination": 0.04, "self_criticism": 0.03},
        },
    },
    {
        "code": "session_length",
        "group": "زمان و انرژی",
        "text": "یک وعده مطالعهٔ خوب برای تو چقدر است؟",
        "options": [
            {"id": "short", "label": "۳۰ تا ۴۵ دقیقه"},
            {"id": "medium", "label": "۶۰ تا ۹۰ دقیقه"},
            {"id": "long", "label": "بیشتر از ۹۰ دقیقه"},
        ],
        "effects": {
            "short": {"routine_preference": -0.02, "novelty_preference": 0.02},
            "medium": {"routine_preference": 0.03},
            "long": {"discipline": 0.03, "routine_preference": 0.02},
        },
    },
    {
        "code": "environment",
        "group": "زمان و انرژی",
        "text": "کجا بهتر تمرکز می‌کنی؟",
        "options": [
            {"id": "home", "label": "خانه"},
            {"id": "library", "label": "کتابخانه/کلاس"},
            {"id": "mix", "label": "فرقی نمی‌کند"},
        ],
        "effects": {
            "home": {"routine_preference": 0.03},
            "library": {"discipline": 0.03, "competition": 0.02},
            "mix": {"novelty_preference": 0.03},
        },
    },
    {
        "code": "test_preference",
        "group": "ترجیح کار سخت/آسان",
        "text": "تست‌های سخت را کِی می‌زنی؟",
        "options": [
            {"id": "first", "label": "اول جلسه، وقتی انرژی دارم"},
            {"id": "middle", "label": "وسط جلسه بعد از گرم شدن"},
            {"id": "last", "label": "آخر جلسه"},
            {"id": "avoid", "label": "تا جای ممکن عقب می‌اندازم"},
        ],
        "effects": {
            "first": {"discipline": 0.04, "stress_tolerance": 0.02},
            "middle": {"routine_preference": 0.03},
            "last": {"procrastination": 0.02},
            "avoid": {"procrastination": 0.05, "self_criticism": 0.02},
        },
    },
    {
        "code": "class_day_energy",
        "group": "روز کلاس",
        "text": "روزهایی که مدرسه/کلاس داری، بعدش چقدر توان داری؟",
        "options": [
            {"id": "high", "label": "خوب، می‌توانم ۲ وعده کار کنم"},
            {"id": "medium", "label": "متوسط، یک وعده کار"},
            {"id": "low", "label": "کم، فقط کار سبک"},
        ],
        "effects": {
            "high": {"energy_baseline": 0.06, "discipline": 0.03},
            "medium": {"energy_baseline": 0.0},
            "low": {"energy_baseline": -0.06, "stress_tolerance": -0.02},
        },
    },
    {
        "code": "fatigue_signal",
        "group": "خستگی",
        "text": "خستگی را معمولاً چطور می‌فهمی؟",
        "options": [
            {"id": "focus", "label": "تمرکزم می‌رود"},
            {"id": "body", "label": "بدنم سنگین می‌شود"},
            {"id": "mood", "label": "بی‌حوصله می‌شوم"},
            {"id": "skip", "label": "متوجه نمی‌شوم تا دیر شود"},
        ],
        "effects": {
            "focus": {"self_awareness": 0.05},
            "body": {"self_awareness": 0.04},
            "mood": {"self_awareness": 0.03},
            "skip": {"self_awareness": -0.05, "stress_tolerance": -0.02},
        },
    },
]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def _find_or_create_subject(db: Session, slug: str, name: str, color: str, order: int) -> models.Subject:
    subject = db.scalars(select(models.Subject).where(models.Subject.slug == slug)).first()
    if subject:
        return subject
    subject = models.Subject(slug=slug, name=name, color=color, order_index=order)
    db.add(subject)
    db.flush()
    return subject


def _insert_nodes(db: Session, book: models.Book, nodes: list[ParsedNode], parent: Optional[models.Topic] = None) -> int:
    count = 0
    for index, node in enumerate(nodes):
        topic = models.Topic(
            book_id=book.id,
            parent_id=parent.id if parent else None,
            node_type=node.node_type,
            title=node.title,
            order_index=index,
            depth=(parent.depth + 1) if parent else 0,
            is_leaf=not node.children,
        )
        db.add(topic)
        db.flush()
        topic.path = (parent.path + f"{parent.id}/") if parent else "/"
        db.flush()
        count += 1
        if parent:
            parent.is_leaf = False
        if node.children:
            count += _insert_nodes(db, book, node.children, topic)
    return count


def _ensure_test_sets(db: Session, book: models.Book, parsed: ParsedBook) -> int:
    leaves = list(
        db.scalars(select(models.Topic).where(models.Topic.book_id == book.id, models.Topic.is_leaf.is_(True)))
    )
    created = 0
    for topic in leaves:
        for level in range(1, max(1, parsed.levels) + 1):
            title = f"بانک تست — {topic.title}"
            if parsed.levels > 1:
                title += f" (سطح {level})"
            exists = db.scalars(
                select(models.TestSet).where(
                    models.TestSet.book_id == book.id,
                    models.TestSet.topic_id == topic.id,
                    models.TestSet.difficulty_level == (level if parsed.levels > 1 else None),
                )
            ).first()
            if exists:
                continue
            db.add(
                models.TestSet(
                    book_id=book.id,
                    topic_id=topic.id,
                    title=title,
                    test_type="normal",
                    difficulty_level=level if parsed.levels > 1 else None,
                    metadata_json={"source": parsed.source_file, "auto_created": True},
                )
            )
            created += 1
    return created


def seed_books(db: Session, content_root: Optional[str] = None) -> dict:
    parsed_books = load_all(content_root)
    if not parsed_books:
        return {"books": 0, "topics": 0, "test_sets": 0, "warning": "فایل محتوای کتاب‌ها پیدا نشد."}
    subjects = {
        entry["slug"]: _find_or_create_subject(db, entry["slug"], entry["name"], entry["color"], entry["order"])
        for entry in SUBJECTS
    }
    stats = {"books": 0, "topics": 0, "test_sets": 0}
    for parsed in parsed_books:
        book = db.scalars(select(models.Book).where(models.Book.stable_key == parsed.stable_key)).first()
        if book is None:
            book = models.Book(
                stable_key=parsed.stable_key,
                title=parsed.title,
                publisher=parsed.publisher,
                subject_id=subjects[parsed.subject_slug].id,
                grade=parsed.grade,
                track=parsed.track,
                hierarchy_note=parsed.hierarchy_note,
                config_version="v3",
            )
            db.add(book)
            db.flush()
            stats["books"] += 1
        else:
            book.hierarchy_note = parsed.hierarchy_note or book.hierarchy_note
        existing_topics = db.scalar(select(func.count(models.Topic.id)).where(models.Topic.book_id == book.id)) or 0
        if not existing_topics:
            stats["topics"] += _insert_nodes(db, book, parsed.chapters)
        stats["test_sets"] += _ensure_test_sets(db, book, parsed)
    db.flush()
    return stats


def seed_default_classes(db: Session, user: models.User) -> int:
    created = 0
    for entry in DEFAULT_CLASSES:
        subject = db.scalars(select(models.Subject).where(models.Subject.slug == entry["slug"])).first()
        if subject is None:
            continue
        exists = db.scalars(
            select(models.ClassSchedule).where(
                models.ClassSchedule.user_id == user.id,
                models.ClassSchedule.title == entry["title"],
            )
        ).first()
        if exists:
            continue
        db.add(
            models.ClassSchedule(
                user_id=user.id,
                subject_id=subject.id,
                title=entry["title"],
                kind="external_class",
                recurring=True,
                source="default_seed_v2",
                notes="روز و ساعت را خودت تعیین کن؛ تا وقتی خالی است در ظرفیت لحاظ نمی‌شود.",
            )
        )
        created += 1
    return created


def seed_badges(db: Session) -> int:
    created = 0
    for code, title, description, condition_type, condition_value, icon in BADGES:
        exists = db.scalars(select(models.Badge).where(models.Badge.code == code)).first()
        if exists:
            continue
        db.add(
            models.Badge(
                code=code,
                title=title,
                description=description,
                condition_type=condition_type,
                condition_value=condition_value,
                icon=icon,
            )
        )
        created += 1
    return created


def seed_onboarding_questions(db: Session) -> int:
    created = 0
    for index, entry in enumerate(ONBOARDING):
        exists = db.scalars(select(models.OnboardingQuestion).where(models.OnboardingQuestion.code == entry["code"])).first()
        if exists:
            continue
        db.add(
            models.OnboardingQuestion(
                code=entry["code"],
                group=entry["group"],
                text=entry["text"],
                kind=entry.get("kind", "single_choice"),
                options=entry.get("options", []),
                effects=entry.get("effects", {}),
                order_index=index,
            )
        )
        created += 1
    return created


RESEARCH_SEED = [
    {
        "source": "Roediger & Karpicke (2006) Test-enhanced learning",
        "title": "Retrieval practice improves long-term retention relative to repeated study",
        "year": 2006,
        "finding": "فعال‌سازی بازیابی در مقایسه با مطالعه مجدد، حافظه بلندمدت را بهتر می‌کند.",
        "limitations": "شرایط آزمایشگاهی؛ تعمیم به برنامه شخصی نیازمند سنجش است.",
        "product_implication": "مرور فعال (ACTIVE_RECALL) به عنوان یک نوع مداخله در موتور پیشنهاد.",
        "evidence_level": "RESEARCH_SUPPORTED",
        "linked_params": ["retention.stability_base_days"],
    },
    {
        "source": "Cepeda et al. (2006) Distributed practice meta-analysis",
        "title": "Spacing effect: distributed practice benefits retention",
        "year": 2006,
        "finding": "فاصله‌گذاری بین تمرین‌ها اثر مثبت متوسط تا بزرگ دارد.",
        "limitations": "بهینه فاصله به فاصله هدف و محتوا وابسته است.",
        "product_implication": "پارامترهای فاصله‌گذاری قابل تنظیم و آزمایش‌شده باشند، نه مقدار جادویی.",
        "evidence_level": "RESEARCH_SUPPORTED",
        "linked_params": ["retention.stability_growth", "review.normal_max_days"],
    },
    {
        "source": "Rohrer & Taylor (2007) Interleaving",
        "title": "Interleaved practice improves mathematics learning",
        "year": 2007,
        "finding": "تمرین متناوب (interleaving) در ریاضیات نتایج بهتری از بلوک‌بندی می‌دهد.",
        "limitations": "احساس دشواری بیشتر برای یادگیرنده.",
        "product_implication": "MIXED_PRACTICE به عنوان نوع مداخله و تنوع موضوعی در جلسات.",
        "evidence_level": "RESEARCH_SUPPORTED",
        "linked_params": [],
    },
    {
        "source": "Dunlosky et al. (2013) Improving students' learning",
        "title": "Practice testing and distributed practice rank highest in utility",
        "year": 2013,
        "finding": "تست تمرینی و تمرین فاصله‌دار بالاترین سودمندی را دارند؛ بازخوانی و برجسته‌سازی کم‌اثرند.",
        "limitations": "کاربردپذیری تحت شرایط مختلف متفاوت است.",
        "product_implication": "موتور تصمیم ابتدا نوع مداخله را انتخاب کند، سپس سؤال را.",
        "evidence_level": "RESEARCH_SUPPORTED",
        "linked_params": ["recommendation.max_suggestions_per_day"],
    },
    {
        "source": "Koriat & Bjork (2005) Illusions of competence",
        "title": "Metacognitive illusions: fluency is mistaken for learning",
        "year": 2005,
        "finding": "سهولت ادراک‌شده لزوماً نشانه یادگیری نیست.",
        "limitations": "مطالعه آزمایشگاهی.",
        "product_implication": "خودگزارشی کاربر باید جدا از داده رفتاری ثبت و با هم مقایسه شود.",
        "evidence_level": "RESEARCH_SUPPORTED",
        "linked_params": [],
    },
]


def seed_research(db: Session) -> int:
    created = 0
    for entry in RESEARCH_SEED:
        exists = db.scalars(select(models.ResearchEntry).where(models.ResearchEntry.title == entry["title"])).first()
        if exists:
            continue
        db.add(models.ResearchEntry(**entry))
        created += 1
    return created


def seed_checkup_coverages(db: Session) -> dict:
    """Chemistry checkups as coverage ranges (V3.1 doc 03) — additive and idempotent."""
    from ..services import checkups

    result = checkups.ensure_coverage_seeded(db)
    db.flush()
    return result


def seed_all(db: Session, user: Optional[models.User] = None, content_root: Optional[str] = None) -> dict:
    result = {
        "books": seed_books(db, content_root),
        "badges": seed_badges(db),
        "onboarding_questions": seed_onboarding_questions(db),
        "research": seed_research(db),
        "checkup_coverages": seed_checkup_coverages(db),
        "default_classes": 0,
    }
    if user is not None:
        result["default_classes"] = seed_default_classes(db, user)
        for book in db.scalars(select(models.Book)):
            exists = db.scalars(
                select(models.UserBookActivation).where(
                    models.UserBookActivation.user_id == user.id, models.UserBookActivation.book_id == book.id
                )
            ).first()
            if not exists:
                db.add(models.UserBookActivation(user_id=user.id, book_id=book.id, active=True))
    db.flush()
    return result
