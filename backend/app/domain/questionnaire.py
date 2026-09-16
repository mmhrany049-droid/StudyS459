"""پرسشنامهٔ تطبیقی — V2.1 (15_ADAPTIVE_QUESTIONNAIRE_V2_1).

- حدود ۴۰ سؤال کوتاه در ۱۰ گروه.
- سؤال بعدی بر اساس uncertainty فعلی انتخاب می‌شود (ابعادی که کمترین
  confidence را دارند بیشترین اطلاعات را می‌دهند).
- انواع: چندگزینه‌ای، مقیاس ۱..۵، سناریویی.
- یک پاسخ منفرد ویژگی را قطعی نمی‌کند (به‌روزرسانی تدریجی در personality.py).

هر گزینه شاهدی 0..1 برای ابعاد مرتبط دارد: {"dimension": value}
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.personality import DIMENSIONS, apply_evidence, get_profile
from app.models import OnboardingAnswer, User

GROUPS = [
    "سبک برنامه‌ریزی", "زمان و انرژی", "شروع کار", "اهمال‌کاری", "واکنش به شکست",
    "فشار و استرس", "انگیزه و پاداش", "عادت خواب/بیداری", "کار سخت/آسان", "انعطاف‌پذیری",
]


def _q(key, group, text, qtype, options=None, scale_labels=None, dimensions=None):
    return {
        "key": key, "group": group, "text": text, "type": qtype,
        "options": options or [], "scale_labels": scale_labels,
        "dimensions": dimensions or [],
    }


# scale: 1..5 — برای ابعاد scale، مقدار شاهد = (answer-1)/4
QUESTIONS = [
    # --- سبک برنامه‌ریزی ---
    _q("plan_style", "سبک برنامه‌ریزی",
       "برای مطالعه معمولاً چه سبکی را ترجیح می‌کنی؟",
       "choice",
       options=[
           {"key": "a", "text": "برنامهٔ دقیق ساعتی", "evidence": {"planning_preference": 0.95, "routine_preference": 0.8}},
           {"key": "b", "text": "لیست کار روزانه بدون ساعت", "evidence": {"planning_preference": 0.6}},
           {"key": "c", "text": "فقط هدف کلی هفتگی", "evidence": {"planning_preference": 0.25}},
           {"key": "d", "text": "بدون برنامه، هر روز هرچه شد", "evidence": {"planning_preference": 0.05, "procrastination": 0.75}},
       ]),
    _q("plan_follow", "سبک برنامه‌ریزی",
       "وقتی برنامه می‌چینی معمولاً چقدر به آن پایبند می‌مانی؟",
       "scale", dimensions=["discipline"]),
    _q("plan_detail", "سبک برنامه‌ریزی",
       "چقدر جزئیات (مبحث، تعداد تست، زمان) در برنامه‌ات مشخص می‌شود؟",
       "scale", dimensions=["planning_preference"]),

    # --- زمان و انرژی ---
    _q("best_time", "زمان و انرژی",
       "در چه بازه‌ای از روز تمرکزت واقعاً بهتر است؟",
       "choice",
       options=[
           {"key": "a", "text": "صبح زود (۶ تا ۹)", "evidence": {}},
           {"key": "b", "text": "میانهٔ روز (۹ تا ۱۳)", "evidence": {}},
           {"key": "c", "text": "عصر (۱۶ تا ۱۹)", "evidence": {}},
           {"key": "d", "text": "شب (۱۹ به بعد)", "evidence": {}},
       ]),
    _q("energy_level", "زمان و انرژی",
       "به‌طور معمول انرژی روزانه‌ات برای درس خواندن چقدر است؟",
       "scale", dimensions=["stress_tolerance"]),
    _q("study_hours", "زمان و انرژی",
       "در یک روز معمولی چند ساعت مطالعهٔ مؤثر واقعی داری؟",
       "choice",
       options=[
           {"key": "a", "text": "کمتر از ۱ ساعت", "evidence": {"goal_orientation": 0.2}},
           {"key": "b", "text": "۱ تا ۲ ساعت", "evidence": {"goal_orientation": 0.4}},
           {"key": "c", "text": "۲ تا ۴ ساعت", "evidence": {"goal_orientation": 0.65}},
           {"key": "d", "text": "بیش از ۴ ساعت", "evidence": {"goal_orientation": 0.9, "discipline": 0.8}},
       ]),
    _q("focus_length", "زمان و انرژی",
       "بدون استراحت چقدر می‌توانی متمرکز بمانی؟",
       "choice",
       options=[
           {"key": "a", "text": "کمتر از ۲۰ دقیقه", "evidence": {"stress_tolerance": 0.25}},
           {"key": "b", "text": "۲۰ تا ۴۰ دقیقه", "evidence": {"stress_tolerance": 0.5}},
           {"key": "c", "text": "۴۰ تا ۷۰ دقیقه", "evidence": {"stress_tolerance": 0.75}},
           {"key": "d", "text": "بیش از ۷۰ دقیقه", "evidence": {"stress_tolerance": 0.95, "discipline": 0.75}},
       ]),

    # --- شروع کار ---
    _q("start_hard", "شروع کار",
       "سخت‌ترین بخش مطالعه برای تو کدام است؟",
       "choice",
       options=[
           {"key": "a", "text": "شروع کردن", "evidence": {"procrastination": 0.85}},
           {"key": "b", "text": "ادامه دادن", "evidence": {"procrastination": 0.5}},
           {"key": "c", "text": "پایان‌بندی و جمع‌بندی", "evidence": {"procrastination": 0.35}},
           {"key": "d", "text": "هیچ‌کدام به‌خصوص", "evidence": {"procrastination": 0.2}},
       ]),
    _q("start_scenario", "شروع کار",
       "«اگر فردا ۶ ساعت وقت آزاد داشته باشی کدام حالت طبیعی‌تر است؟»",
       "choice",
       options=[
           {"key": "a", "text": "از صبح شروع می‌کنم", "evidence": {"discipline": 0.9, "procrastination": 0.15}},
           {"key": "b", "text": "با کار ساده شروع می‌کنم", "evidence": {"novelty_preference": 0.4, "procrastination": 0.45}},
           {"key": "c", "text": "شروع را عقب می‌اندازم", "evidence": {"procrastination": 0.9}},
           {"key": "d", "text": "بستگی به انرژی دارد", "evidence": {"procrastination": 0.5}},
       ]),
    _q("start_small", "شروع کار",
       "شروع با یک قدم کوچک (مثلاً ۵ تست) به نظرت کمک می‌کند؟",
       "choice",
       options=[
           {"key": "a", "text": "بله، خیلی", "evidence": {"reward_sensitivity": 0.6, "procrastination": 0.6}},
           {"key": "b", "text": "کمی", "evidence": {"reward_sensitivity": 0.45}},
           {"key": "c", "text": "نه، دوست دارم مستقیم سر اصل مطلب", "evidence": {"goal_orientation": 0.7}},
       ]),

    # --- اهمال‌کاری ---
    _q("procrastinate_freq", "اهمال‌کاری",
       "چقدر کارهای درسی را به «بعداً» می‌اندازی؟",
       "scale", dimensions=["procrastination"]),
    _q("procrastinate_trigger", "اهمال‌کاری",
       "معمولاً چی باعث می‌شود کار را عقب بیندازی؟",
       "choice",
       options=[
           {"key": "a", "text": "سختی یا خستگی", "evidence": {"procrastination": 0.7, "stress_tolerance": 0.35}},
           {"key": "b", "text": "حواس‌پرتی (گوشی/بازی)", "evidence": {"procrastination": 0.75, "discipline": 0.3}},
           {"key": "c", "text": "بی‌انگیزگی", "evidence": {"procrastination": 0.65, "goal_orientation": 0.3}},
           {"key": "d", "text": "کمتر عقب می‌اندازم", "evidence": {"procrastination": 0.15, "discipline": 0.8}},
       ]),
    _q("deadline_mode", "اهمال‌کاری",
       "با ددلاین‌ها چطور عمل می‌کنی؟",
       "choice",
       options=[
           {"key": "a", "text": "از اول شروع می‌کنم و زود تمام می‌کنم", "evidence": {"discipline": 0.9}},
           {"key": "b", "text": "منظم اما آرام", "evidence": {"discipline": 0.6}},
           {"key": "c", "text": "در روزهای آخر فشرده", "evidence": {"procrastination": 0.7, "stress_tolerance": 0.6}},
       ]),

    # --- واکنش به شکست ---
    _q("fail_reaction", "واکنش به شکست",
       "بعد از یک نتیجهٔ بد در آزمون چه حسی داری؟",
       "choice",
       options=[
           {"key": "a", "text": "خیلی ناراحت می‌شوم و مدتها ذهنم درگیر است", "evidence": {"self_criticism": 0.9, "stress_tolerance": 0.3}},
           {"key": "b", "text": "ناراحت می‌شوم اما ادامه می‌دهم", "evidence": {"self_criticism": 0.55, "stress_tolerance": 0.6}},
           {"key": "c", "text": "سریع رد می‌شوم و دوباره تلاش می‌کنم", "evidence": {"self_criticism": 0.25, "stress_tolerance": 0.85}},
       ]),
    _q("fail_recover", "واکنش به شکست",
       "بعد از شکست چقدر سریع به مسیر برمی‌گردی؟",
       "scale", dimensions=["stress_tolerance"]),
    _q("self_blame", "واکنش به شکست",
       "وقتی برنامه‌ات به‌هم می‌ریزد چقدر خودت را سرزنش می‌کنی؟",
       "scale", dimensions=["self_criticism"]),

    # --- فشار و استرس ---
    _q("stress_level", "فشار و استرس",
       "میزان استرس روزانهٔ تو دربارهٔ درس و کنکور چقدر است؟",
       "scale", dimensions=["stress_tolerance"], ),
    _q("stress_cope", "فشار و استرس",
       "زمان امتحانات چطور مدیریت می‌شوی؟",
       "choice",
       options=[
           {"key": "a", "text": "برنامه‌ریزی و آرامش", "evidence": {"stress_tolerance": 0.85, "discipline": 0.7}},
           {"key": "b", "text": "استرس سالم و پشتکار", "evidence": {"stress_tolerance": 0.6}},
           {"key": "c", "text": "استرس زیاد و بی‌خوابی", "evidence": {"stress_tolerance": 0.2}},
       ]),
    _q("overload", "فشار و استرس",
       "وقتی کارها انبار می‌شود اولین واکنشت چیست؟",
       "choice",
       options=[
           {"key": "a", "text": "لیست می‌کنم و شروع می‌کنم", "evidence": {"discipline": 0.85, "planning_preference": 0.7}},
           {"key": "b", "text": "خسته می‌شوم و فرار می‌کنم", "evidence": {"procrastination": 0.8, "stress_tolerance": 0.3}},
           {"key": "c", "text": "خشمگین ولی انجام می‌دهم", "evidence": {"stress_tolerance": 0.5, "goal_orientation": 0.6}},
       ]),

    # --- انگیزه و پاداش ---
    _q("reward_effect", "انگیزه و پاداش",
       "امتیاز، سکه و زنجیرهٔ روزهای پیاپی چقدر روی تو اثر دارد؟",
       "scale", dimensions=["reward_sensitivity"]),
    _q("motivation_source", "انگیزه و پاداش",
       "بیشترین انگیزه‌ات از کجا می‌آید؟",
       "choice",
       options=[
           {"key": "a", "text": "رتبه و رقابت", "evidence": {"competition": 0.9, "goal_orientation": 0.8}},
           {"key": "b", "text": "پیشرفت شخصی", "evidence": {"competition": 0.3, "goal_orientation": 0.8}},
           {"key": "c", "text": "رضایت خانواده", "evidence": {"competition": 0.3, "reward_sensitivity": 0.6}},
           {"key": "d", "text": "کنجکاوی به خود درس", "evidence": {"novelty_preference": 0.7, "goal_orientation": 0.6}},
       ]),
    _q("streak_effect", "انگیزه و پاداش",
       "اگر زنجیرهٔ روزهای پیاپی‌ات قطع شود چه می‌شود؟",
       "choice",
       options=[
           {"key": "a", "text": "سریع دوباره شروع می‌کنم", "evidence": {"reward_sensitivity": 0.7, "discipline": 0.7}},
           {"key": "b", "text": "خیلی دلسرد می‌شوم", "evidence": {"self_criticism": 0.7, "reward_sensitivity": 0.8}},
           {"key": "c", "text": "برایم مهم نیست", "evidence": {"reward_sensitivity": 0.2}},
       ]),

    # --- عادت خواب/بیداری ---
    _q("sleep_time", "عادت خواب/بیداری",
       "معمولاً چند می‌خوابی؟",
       "choice",
       options=[
           {"key": "a", "text": "قبل از ۲۲:۳۰", "evidence": {"discipline": 0.85}},
           {"key": "b", "text": "۲۲:۳۰ تا ۲۳:۳۰", "evidence": {"discipline": 0.6}},
           {"key": "c", "text": "بعد از نیمه‌شب", "evidence": {"discipline": 0.25, "procrastination": 0.6}},
       ]),
    _q("wake_style", "عادت خواب/بیداری",
       "صبح‌ها بیدار شدن برایت چگونه است؟",
       "choice",
       options=[
           {"key": "a", "text": "آسان و سریع", "evidence": {"discipline": 0.8}},
           {"key": "b", "text": "با زحمت", "evidence": {"discipline": 0.45}},
           {"key": "c", "text": "خیلی سخت", "evidence": {"discipline": 0.2}},
       ]),

    # --- کار سخت/آسان ---
    _q("hard_first", "کار سخت/آسان",
       "وقتی هم کار سخت و هم آسان داری، کدام را اول انجام می‌دهی؟",
       "choice",
       options=[
           {"key": "a", "text": "سخت را اول (تا راحت شوم)", "evidence": {"discipline": 0.85, "procrastination": 0.2}},
           {"key": "b", "text": "آسان را اول (برای گرم شدن)", "evidence": {"procrastination": 0.5, "novelty_preference": 0.4}},
           {"key": "c", "text": "هر چه سخت‌تر باشد بیشتر عقب می‌افتد", "evidence": {"procrastination": 0.9}},
       ]),
    _q("hard_subject", "کار سخت/آسان",
       "با درس سخت‌ات چطور روبه‌رو می‌شوی؟",
       "scale", dimensions=["stress_tolerance"]),
    _q("chunk_pref", "کار سخت/آسان",
       "کارهای کوچک‌تر را ترجیح می‌دهی یا وعده‌های بزرگ‌تر؟",
       "choice",
       options=[
           {"key": "a", "text": "کارهای کوچک متعدد", "evidence": {"reward_sensitivity": 0.6, "routine_preference": 0.5}},
           {"key": "b", "text": "وعده‌های بزرگ متمرکز", "evidence": {"goal_orientation": 0.7, "stress_tolerance": 0.6}},
           {"key": "c", "text": "بستگی به روز دارد", "evidence": {"novelty_preference": 0.6}},
       ]),

    # --- انعطاف‌پذیری ---
    _q("flex_plan", "انعطاف‌پذیری",
       "وقتی برنامه‌ات به‌هم می‌خورد چه می‌کنی؟",
       "choice",
       options=[
           {"key": "a", "text": "سریع برنامهٔ جایگزین می‌چینم", "evidence": {"planning_preference": 0.8, "stress_tolerance": 0.7}},
           {"key": "b", "text": "همان روز را نیمه‌تعطیل می‌کنم", "evidence": {"procrastination": 0.6}},
           {"key": "c", "text": "کل هفته را به‌هم می‌ریزم", "evidence": {"procrastination": 0.8, "routine_preference": 0.8}},
       ]),
    _q("routine_vs_new", "انعطاف‌پذیری",
       "روتین ثابت روزانه یا تنوع؟",
       "choice",
       options=[
           {"key": "a", "text": "روتین ثابت", "evidence": {"routine_preference": 0.9, "novelty_preference": 0.2}},
           {"key": "b", "text": "ترکیبی", "evidence": {"routine_preference": 0.5, "novelty_preference": 0.5}},
           {"key": "c", "text": "تنوع و تازگی", "evidence": {"routine_preference": 0.15, "novelty_preference": 0.9}},
       ]),
    _q("change_tolerance", "انعطاف‌پذیری",
       "با تغییر ناگهانی شرایط (مثلاً مهمان/خارج رفتن) چقدر راحت برنامه را عوض می‌کنی؟",
       "scale", dimensions=["novelty_preference"]),
    _q("goal_setting", "انعطاف‌پذیری",
       "برای هفته هدف عددی مشخص (مثلاً ۲۰۰ تست) تعیین می‌کنی؟",
       "choice",
       options=[
           {"key": "a", "text": "همیشه", "evidence": {"goal_orientation": 0.9, "planning_preference": 0.8}},
           {"key": "b", "text": "بعضی وقت‌ها", "evidence": {"goal_orientation": 0.5}},
           {"key": "c", "text": "هرگز", "evidence": {"goal_orientation": 0.15}},
       ]),
]

QUESTION_MAP = {q["key"]: q for q in QUESTIONS}
TOTAL = len(QUESTIONS)  # ~۴۰ سؤال


def answered_keys(db: Session, user_id: int) -> set[str]:
    return set(db.scalars(
        select(OnboardingAnswer.question_key).where(OnboardingAnswer.user_id == user_id)))


def next_question(db: Session, user: User) -> dict | None:
    """Adaptive Flow: انتخاب سؤال بعدی بر اساس uncertainty.

    ۱) فقط سؤالات بی‌پاسخ.
    ۲) امتیاز سؤال = مجموع (۱ - confidence) ابعادی که آن سؤال روشن می‌کند.
    ۳) ترجیح گروه‌هایی که هنوز سؤال کمتری ازشان پرسیده شده (پراکندگی).
    """
    answered = answered_keys(db, user.id)
    remaining = [q for q in QUESTIONS if q["key"] not in answered]
    if not remaining:
        return None
    profile = get_profile(db, user)

    group_counts: dict[str, int] = {}
    for q in QUESTIONS:
        if q["key"] in answered:
            group_counts[q["group"]] = group_counts.get(q["group"], 0) + 1

    def uncertainty(q) -> float:
        dims = q["dimensions"]
        if not dims:
            # سؤالات گزینه‌ای: ابعاد از evidence گزینه‌ها
            dims = list({d for o in q["options"] for d in o.get("evidence", {})})
        total = 0.0
        for d in dims:
            dim = profile.personality_json.get(d) or {}
            total += 1.0 - dim.get("confidence", 0.0)
        return total

    def group_bonus(q) -> float:
        # گروه‌های کم‌پرسیده‌شده اولویت پراکندگی دارند
        c = group_counts.get(q["group"], 0)
        return 0.15 * max(0, 2 - c)

    best = max(remaining, key=lambda q: uncertainty(q) + group_bonus(q))
    return best


def apply_answer(db: Session, user: User, question_key: str, answer_key) -> dict:
    """ثبت پاسخ + به‌روزرسانی تدریجی مدل (بدون قطعی‌کردن از یک پاسخ)."""
    q = QUESTION_MAP.get(question_key)
    if q is None:
        return {"ok": False, "reason": "unknown_question"}
    if q["type"] == "scale":
        try:
            val = int(answer_key)
        except (TypeError, ValueError):
            return {"ok": False, "reason": "invalid_answer"}
        if not (1 <= val <= 5):
            return {"ok": False, "reason": "invalid_answer"}
        evidence_val = (val - 1) / 4
        for d in q["dimensions"]:
            apply_evidence(db, user, d, evidence_val, source="self_report")
    else:
        opt = next((o for o in q["options"] if o["key"] == answer_key), None)
        if opt is None:
            return {"ok": False, "reason": "invalid_answer"}
        for d, v in opt.get("evidence", {}).items():
            if d in DIMENSIONS:
                apply_evidence(db, user, d, v, source="self_report")
        # ترجیح زمانی مطالعه در preferences (نه personality)
        if question_key == "best_time":
            p = get_profile(db, user)
            prefs = dict(p.preferences_json or {})
            label = opt["text"]
            prefs["preferred_study_time"] = {
                "value": label, "confidence": 0.9, "evidence_count": 1,
                "source": "self_report",
            }
            p.preferences_json = prefs

    existing = db.execute(
        select(OnboardingAnswer).where(OnboardingAnswer.user_id == user.id,
                                       OnboardingAnswer.question_key == question_key)
    ).scalar_one_or_none()
    if existing is None:
        db.add(OnboardingAnswer(user_id=user.id, question_key=question_key,
                                answer_key=str(answer_key)))
    else:
        existing.answer_key = str(answer_key)
    return {"ok": True}


def summary(db: Session, user: User) -> dict:
    answered = answered_keys(db, user.id)
    return {
        "total": TOTAL,
        "answered": len(answered),
        "remaining": TOTAL - len(answered),
        "complete": len(answered) >= TOTAL,
    }
