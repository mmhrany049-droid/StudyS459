"""
پرسش‌نامه تطبیقی — سند 15_ADAPTIVE_QUESTIONNAIRE_V2_1 و 14_USER_PROFILE_AND_PERSONALITY_V2_1

اصول سند:
- سوال بعدی بر اساس بیشترین عدم‌قطعیت (uncertainty) انتخاب می‌شود، نه ترتیب ثابت.
- یک پاسخ منفرد نباید یک ویژگی را قطعی کند.
- self-report جدا از observed behavior نگه داشته می‌شود.
- خروجی «تشخیص روان‌شناختی» نیست؛ فقط مدل کاربردی برای برنامه‌ریزی.
- هر ویژگی: value + confidence + evidence_count (سند ۲۲).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m

# ده بُعد سند ۱۴ (همه در بازه ۰..۱)
TRAITS = [
    "discipline", "planning_preference", "procrastination", "competition",
    "reward_sensitivity", "stress_tolerance", "routine_preference",
    "novelty_preference", "self_criticism", "goal_orientation",
]

TRAIT_LABELS = {
    "discipline": "نظم و پایبندی",
    "planning_preference": "ترجیح برنامه‌ریزی",
    "procrastination": "اهمال‌کاری",
    "competition": "رقابت‌جویی",
    "reward_sensitivity": "حساسیت به پاداش",
    "stress_tolerance": "تحمل فشار",
    "routine_preference": "ترجیح روتین",
    "novelty_preference": "ترجیح تنوع",
    "self_criticism": "خودانتقادی",
    "goal_orientation": "هدف‌محوری",
}

# راهنمای تفسیر: هر بُعد در دو سر طیف چه معنایی برای برنامه‌ریزی دارد
TRAIT_POLES = {
    "discipline": ("نیاز به یادآوری بیشتر", "پایبندی بالا به برنامه"),
    "planning_preference": ("ترجیح انعطاف", "ترجیح برنامه دقیق"),
    "procrastination": ("شروع‌کننده سریع", "تمایل به تعویق"),
    "competition": ("رقابت بی‌اثر", "رقابت انگیزه‌بخش"),
    "reward_sensitivity": ("پاداش کم‌اثر", "پاداش پرانگیزه"),
    "stress_tolerance": ("حساس به فشار", "مقاوم در فشار"),
    "routine_preference": ("ترجیح تغییر", "ترجیح روال ثابت"),
    "novelty_preference": ("تمرکز بر تکرار", "نیاز به تنوع"),
    "self_criticism": ("پذیرش اشتباه", "سخت‌گیری با خود"),
    "goal_orientation": ("روزمره‌محور", "هدف‌محور بلندمدت"),
}

# ---------------------------------------------------------------- بانک سوال
# هر گزینه برای هر بُعد یک مقدار ۰..۱ می‌دهد (weight = شدت شاهد).
# گروه‌ها مطابق سند ۱۵.
QUESTIONS: list[dict] = [
    {
        "code": "q_free_day",
        "group": "شروع کار",
        "kind": "scenario",
        "text": "اگر فردا ۶ ساعت وقت آزاد داشته باشی، کدام حالت طبیعی‌تر است؟",
        "options": [
            {"key": "a", "label": "از صبح زود شروع می‌کنم",
             "scores": {"procrastination": 0.1, "discipline": 0.85, "planning_preference": 0.7}},
            {"key": "b", "label": "با یک کار ساده شروع می‌کنم تا راه بیفتم",
             "scores": {"procrastination": 0.4, "discipline": 0.6, "planning_preference": 0.5}},
            {"key": "c", "label": "شروع را عقب می‌اندازم",
             "scores": {"procrastination": 0.85, "discipline": 0.25, "planning_preference": 0.3}},
            {"key": "d", "label": "بستگی به انرژی آن روز دارد",
             "scores": {"procrastination": 0.5, "planning_preference": 0.25, "routine_preference": 0.25}},
        ],
    },
    {
        "code": "q_plan_style",
        "group": "سبک برنامه‌ریزی",
        "kind": "multi",
        "text": "کدام نوع برنامه برایت بهتر جواب می‌دهد؟",
        "options": [
            {"key": "a", "label": "برنامه ساعت‌به‌ساعت و دقیق",
             "scores": {"planning_preference": 0.95, "routine_preference": 0.8, "novelty_preference": 0.2}},
            {"key": "b", "label": "لیست کارهای روز بدون ساعت مشخص",
             "scores": {"planning_preference": 0.6, "routine_preference": 0.5}},
            {"key": "c", "label": "فقط یکی دو هدف مهم روز",
             "scores": {"planning_preference": 0.35, "goal_orientation": 0.7}},
            {"key": "d", "label": "بدون برنامه، هرچه پیش آید",
             "scores": {"planning_preference": 0.1, "routine_preference": 0.2, "novelty_preference": 0.75}},
        ],
    },
    {
        "code": "q_energy_peak",
        "group": "زمان و انرژی",
        "kind": "multi",
        "text": "معمولاً در چه زمانی بهترین تمرکز را داری؟",
        "options": [
            {"key": "a", "label": "صبح زود", "scores": {"discipline": 0.75, "routine_preference": 0.7}},
            {"key": "b", "label": "بعدازظهر", "scores": {"routine_preference": 0.5}},
            {"key": "c", "label": "شب", "scores": {"routine_preference": 0.4, "procrastination": 0.6}},
            {"key": "d", "label": "ثابت نیست", "scores": {"routine_preference": 0.2, "novelty_preference": 0.7}},
        ],
    },
    {
        "code": "q_hard_first",
        "group": "ترجیح کار سخت/آسان",
        "kind": "multi",
        "text": "وقتی چند کار داری، معمولاً از کجا شروع می‌کنی؟",
        "options": [
            {"key": "a", "label": "سخت‌ترین کار را اول انجام می‌دهم",
             "scores": {"discipline": 0.9, "procrastination": 0.15, "goal_orientation": 0.8}},
            {"key": "b", "label": "چند کار آسان تا گرم شوم",
             "scores": {"discipline": 0.5, "procrastination": 0.5}},
            {"key": "c", "label": "هرچه ددلاینش نزدیک‌تر است",
             "scores": {"planning_preference": 0.45, "procrastination": 0.6, "goal_orientation": 0.5}},
            {"key": "d", "label": "هرچه حوصله‌اش را دارم",
             "scores": {"discipline": 0.25, "procrastination": 0.7, "novelty_preference": 0.6}},
        ],
    },
    {
        "code": "q_after_fail",
        "group": "واکنش به شکست",
        "kind": "scenario",
        "text": "یک آزمون را بد می‌دهی. واکنش معمول تو چیست؟",
        "options": [
            {"key": "a", "label": "همان روز اشتباهاتم را مرور می‌کنم",
             "scores": {"discipline": 0.85, "self_criticism": 0.55, "goal_orientation": 0.8}},
            {"key": "b", "label": "ناراحت می‌شوم ولی ادامه می‌دهم",
             "scores": {"stress_tolerance": 0.6, "self_criticism": 0.5}},
            {"key": "c", "label": "خیلی به خودم سخت می‌گیرم",
             "scores": {"self_criticism": 0.95, "stress_tolerance": 0.25}},
            {"key": "d", "label": "چند روز از آن درس فاصله می‌گیرم",
             "scores": {"self_criticism": 0.4, "stress_tolerance": 0.35, "procrastination": 0.7}},
        ],
    },
    {
        "code": "q_pressure",
        "group": "فشار و استرس",
        "kind": "scale",
        "text": "نزدیک امتحان، فشار چه اثری روی کارت دارد؟",
        "options": [
            {"key": "1", "label": "کاملاً از کار می‌افتم", "scores": {"stress_tolerance": 0.05}},
            {"key": "2", "label": "خیلی سخت می‌شود", "scores": {"stress_tolerance": 0.3}},
            {"key": "3", "label": "فرقی نمی‌کند", "scores": {"stress_tolerance": 0.55}},
            {"key": "4", "label": "کمی سریع‌تر می‌شوم", "scores": {"stress_tolerance": 0.8}},
            {"key": "5", "label": "بهترین عملکردم زیر فشار است", "scores": {"stress_tolerance": 0.97}},
        ],
    },
    {
        "code": "q_reward",
        "group": "انگیزه و پاداش",
        "kind": "scale",
        "text": "گرفتن سکه/امتیاز چقدر تو را به ادامه دادن تشویق می‌کند؟",
        "options": [
            {"key": "1", "label": "اصلاً", "scores": {"reward_sensitivity": 0.05}},
            {"key": "2", "label": "کم", "scores": {"reward_sensitivity": 0.3}},
            {"key": "3", "label": "متوسط", "scores": {"reward_sensitivity": 0.55}},
            {"key": "4", "label": "زیاد", "scores": {"reward_sensitivity": 0.8}},
            {"key": "5", "label": "خیلی زیاد", "scores": {"reward_sensitivity": 0.97}},
        ],
    },
    {
        "code": "q_competition",
        "group": "انگیزه و پاداش",
        "kind": "multi",
        "text": "مقایسه شدن با دیگران چه اثری روی تو دارد؟",
        "options": [
            {"key": "a", "label": "انگیزه‌ام زیاد می‌شود",
             "scores": {"competition": 0.95, "stress_tolerance": 0.65}},
            {"key": "b", "label": "کمی تأثیر مثبت دارد", "scores": {"competition": 0.65}},
            {"key": "c", "label": "بی‌تفاوتم", "scores": {"competition": 0.3}},
            {"key": "d", "label": "اذیتم می‌کند",
             "scores": {"competition": 0.05, "stress_tolerance": 0.3, "self_criticism": 0.7}},
        ],
    },
    {
        "code": "q_routine",
        "group": "انعطاف‌پذیری",
        "kind": "multi",
        "text": "اگر برنامه‌ات یک روز به هم بخورد چه می‌کنی؟",
        "options": [
            {"key": "a", "label": "همان روز جبران می‌کنم",
             "scores": {"discipline": 0.9, "routine_preference": 0.75, "goal_orientation": 0.8}},
            {"key": "b", "label": "روز بعد جبران می‌کنم", "scores": {"discipline": 0.65, "routine_preference": 0.55}},
            {"key": "c", "label": "برنامه را عوض می‌کنم",
             "scores": {"planning_preference": 0.35, "novelty_preference": 0.7, "routine_preference": 0.25}},
            {"key": "d", "label": "معمولاً کل برنامه از دستم در می‌رود",
             "scores": {"discipline": 0.15, "procrastination": 0.85, "routine_preference": 0.2}},
        ],
    },
    {
        "code": "q_variety",
        "group": "انعطاف‌پذیری",
        "kind": "multi",
        "text": "در یک جلسه مطالعه ترجیح می‌دهی...",
        "options": [
            {"key": "a", "label": "فقط روی یک مبحث تمرکز کنم",
             "scores": {"novelty_preference": 0.1, "routine_preference": 0.85}},
            {"key": "b", "label": "دو مبحث نزدیک به هم", "scores": {"novelty_preference": 0.4}},
            {"key": "c", "label": "چند درس مختلف را تغییر دهم",
             "scores": {"novelty_preference": 0.9, "routine_preference": 0.2}},
        ],
    },
    {
        "code": "q_sleep",
        "group": "عادت خواب/بیداری",
        "kind": "multi",
        "text": "ساعت خواب و بیداری‌ات چقدر ثابت است؟",
        "options": [
            {"key": "a", "label": "تقریباً هر روز ثابت",
             "scores": {"routine_preference": 0.9, "discipline": 0.8}},
            {"key": "b", "label": "در روزهای مدرسه ثابت", "scores": {"routine_preference": 0.6, "discipline": 0.6}},
            {"key": "c", "label": "خیلی متغیر",
             "scores": {"routine_preference": 0.15, "discipline": 0.3, "procrastination": 0.7}},
        ],
    },
    {
        "code": "q_goal",
        "group": "هدف",
        "kind": "multi",
        "text": "کدام جمله به تو نزدیک‌تر است؟",
        "options": [
            {"key": "a", "label": "هدف بلندمدت مشخصی دارم و برایش تلاش می‌کنم",
             "scores": {"goal_orientation": 0.95, "discipline": 0.75}},
            {"key": "b", "label": "هدف دارم ولی گاهی گم می‌شود", "scores": {"goal_orientation": 0.6}},
            {"key": "c", "label": "بیشتر روزبه‌روز جلو می‌روم",
             "scores": {"goal_orientation": 0.25, "planning_preference": 0.3}},
        ],
    },
    {
        "code": "q_start_delay",
        "group": "اهمال‌کاری",
        "kind": "scale",
        "text": "از لحظه‌ای که می‌نشینی تا شروع واقعی مطالعه چقدر طول می‌کشد؟",
        "options": [
            {"key": "1", "label": "تقریباً بلافاصله", "scores": {"procrastination": 0.05, "discipline": 0.9}},
            {"key": "2", "label": "حدود ۵ دقیقه", "scores": {"procrastination": 0.25, "discipline": 0.7}},
            {"key": "3", "label": "حدود ۱۵ دقیقه", "scores": {"procrastination": 0.5, "discipline": 0.5}},
            {"key": "4", "label": "حدود نیم ساعت", "scores": {"procrastination": 0.75, "discipline": 0.3}},
            {"key": "5", "label": "بیشتر از نیم ساعت", "scores": {"procrastination": 0.95, "discipline": 0.15}},
        ],
    },
    {
        "code": "q_deadline",
        "group": "اهمال‌کاری",
        "kind": "scenario",
        "text": "کاری که ددلاینش یک هفته دیگر است را معمولاً کی انجام می‌دهی؟",
        "options": [
            {"key": "a", "label": "همان روزهای اول", "scores": {"procrastination": 0.1, "planning_preference": 0.8}},
            {"key": "b", "label": "وسط هفته", "scores": {"procrastination": 0.45}},
            {"key": "c", "label": "شب آخر", "scores": {"procrastination": 0.9, "stress_tolerance": 0.7}},
        ],
    },
    {
        "code": "q_break",
        "group": "زمان و انرژی",
        "kind": "multi",
        "text": "جلسه مطالعه ایده‌آل تو چقدر است؟",
        "options": [
            {"key": "a", "label": "کوتاه (۲۵–۳۰ دقیقه) با استراحت",
             "scores": {"stress_tolerance": 0.4, "novelty_preference": 0.6}},
            {"key": "b", "label": "متوسط (۴۵–۶۰ دقیقه)", "scores": {"discipline": 0.65, "routine_preference": 0.6}},
            {"key": "c", "label": "طولانی (بیش از ۹۰ دقیقه)",
             "scores": {"discipline": 0.85, "stress_tolerance": 0.75, "novelty_preference": 0.2}},
        ],
    },
]

QUESTION_BY_CODE = {q["code"]: q for q in QUESTIONS}

# هر پاسخ چقدر «شاهد» می‌آورد؛ برای رسیدن به اطمینان کامل چند شاهد لازم است.
EVIDENCE_FULL = 4.0     # ۴ شاهد برای یک بُعد ≈ اطمینان بالا
PRIOR = 0.5             # باور اولیه خنثی


def _trait_evidence(db: Session, user_id: int) -> dict[str, list[float]]:
    """شواهد هر بُعد را از پاسخ‌های ثبت‌شده بازسازی می‌کند."""
    rows = db.scalars(select(m.OnboardingAnswer).where(
        m.OnboardingAnswer.user_id == user_id)).all()
    ev: dict[str, list[float]] = {t: [] for t in TRAITS}
    for r in rows:
        q = QUESTION_BY_CODE.get(r.question_code)
        if not q:
            continue
        opt = next((o for o in q["options"] if o["key"] == r.answer_value), None)
        if not opt:
            continue
        for trait, val in opt["scores"].items():
            if trait in ev:
                ev[trait].append(float(val))
    return ev


def profile(db: Session, user_id: int) -> dict:
    """
    مدل شخصیت با value/confidence/evidence_count برای هر بُعد (سند ۲۲).
    یک پاسخ منفرد ویژگی را قطعی نمی‌کند: مقدار به سمت PRIOR منقبض می‌شود.
    """
    ev = _trait_evidence(db, user_id)
    answered = db.scalar(select(m.OnboardingAnswer).where(
        m.OnboardingAnswer.user_id == user_id)) is not None
    traits = {}
    for t in TRAITS:
        vals = ev[t]
        n = len(vals)
        raw = sum(vals) / n if n else PRIOR
        # انقباض به سمت باور اولیه متناسب با کمبود شاهد (shrinkage)
        w = n / (n + 2.0)
        value = PRIOR + (raw - PRIOR) * w
        conf = min(1.0, n / EVIDENCE_FULL)
        lo, hi = TRAIT_POLES[t]
        traits[t] = {
            "key": t,
            "label": TRAIT_LABELS[t],
            "value": round(value, 3),
            "confidence": round(conf, 2),
            "evidence_count": n,
            "low_label": lo,
            "high_label": hi,
            "reliable": conf >= 0.5,
        }
    total_ans = sum(len(v) for v in ev.values())
    overall = (sum(t["confidence"] for t in traits.values()) / len(TRAITS)) if TRAITS else 0.0
    return {
        "traits": list(traits.values()),
        "answered_questions": _answered_count(db, user_id),
        "total_questions": len(QUESTIONS),
        "evidence_total": total_ans,
        "overall_confidence": round(overall, 2),
        "started": answered,
        "source": "self_report",
        "disclaimer": "این پرسش‌نامه تشخیص روان‌شناختی نیست؛ فقط یک مدل کاربردی برای تنظیم برنامه است.",
    }


def _answered_count(db: Session, user_id: int) -> int:
    rows = db.scalars(select(m.OnboardingAnswer.question_code).where(
        m.OnboardingAnswer.user_id == user_id)).all()
    return len({r for r in rows if r in QUESTION_BY_CODE})


def _answered_codes(db: Session, user_id: int) -> set[str]:
    return set(db.scalars(select(m.OnboardingAnswer.question_code).where(
        m.OnboardingAnswer.user_id == user_id)).all())


def next_question(db: Session, user_id: int) -> dict | None:
    """
    انتخاب تطبیقی: سوالی که بیشترین کمک را به کاهش عدم‌قطعیت می‌کند.
    امتیاز هر سوال = مجموع کمبود اطمینان ابعادی که لمس می‌کند.
    """
    done = _answered_codes(db, user_id)
    ev = _trait_evidence(db, user_id)
    remaining = [q for q in QUESTIONS if q["code"] not in done]
    if not remaining:
        return None

    def gain(q: dict) -> float:
        touched: set[str] = set()
        for o in q["options"]:
            touched |= set(o["scores"].keys())
        g = 0.0
        for t in touched:
            n = len(ev.get(t, []))
            g += max(0.0, 1.0 - n / EVIDENCE_FULL)
        # سوالی که چند بُعد کم‌شاهد را هم‌زمان پوشش دهد ارزش بیشتری دارد
        return g

    best = max(remaining, key=lambda q: (gain(q), -QUESTIONS.index(q)))
    return {
        "code": best["code"],
        "group": best["group"],
        "kind": best["kind"],
        "text": best["text"],
        "options": [{"key": o["key"], "label": o["label"]} for o in best["options"]],
        "answered": _answered_count(db, user_id),
        "total": len(QUESTIONS),
        "information_gain": round(gain(best), 2),
    }


def save_answer(db: Session, user_id: int, code: str, value: str) -> dict:
    q = QUESTION_BY_CODE.get(code)
    if not q:
        raise ValueError("سوال یافت نشد.")
    if not any(o["key"] == value for o in q["options"]):
        raise ValueError("گزینه نامعتبر است.")
    row = db.scalar(select(m.OnboardingAnswer).where(
        m.OnboardingAnswer.user_id == user_id,
        m.OnboardingAnswer.question_code == code))
    if row:
        row.answer_value = value           # تغییر پاسخ مجاز است
        row.created_at = datetime.utcnow()
    else:
        db.add(m.OnboardingAnswer(user_id=user_id, question_code=code,
                                  answer_value=value))
    db.flush()
    return {"saved": True, "code": code}


def reset(db: Session, user_id: int) -> dict:
    rows = db.scalars(select(m.OnboardingAnswer).where(
        m.OnboardingAnswer.user_id == user_id)).all()
    for r in rows:
        db.delete(r)
    db.flush()
    return {"deleted": len(rows)}


def planning_hints(db: Session, user_id: int) -> list[dict]:
    """
    ترجمه مدل به توصیه عملی برنامه‌ریزی.
    فقط ابعادی که اطمینان کافی دارند (reliable) پیشنهاد می‌دهند.
    """
    p = profile(db, user_id)
    by = {t["key"]: t for t in p["traits"]}
    out: list[dict] = []

    def add(trait: str, cond: bool, text: str):
        t = by[trait]
        if t["reliable"] and cond:
            out.append({"trait": trait, "label": t["label"],
                        "confidence": t["confidence"], "text": text})

    add("procrastination", by["procrastination"]["value"] > 0.65,
        "کارها با حجم کوچک‌تر شروع شوند تا شروع آسان شود؛ اولین کار روز سبک باشد.")
    add("procrastination", by["procrastination"]["value"] < 0.35,
        "می‌توانی سخت‌ترین کار را اول روز بگذاری.")
    add("planning_preference", by["planning_preference"]["value"] > 0.65,
        "برنامه با ترتیب مشخص و تعداد دقیق تست نمایش داده شود.")
    add("planning_preference", by["planning_preference"]["value"] < 0.35,
        "برنامه به‌صورت چند هدف کلیدی روز ارائه شود، نه جدول ساعتی.")
    add("stress_tolerance", by["stress_tolerance"]["value"] < 0.35,
        "نزدیک امتحان حجم روزانه کمتر و مرور بیشتر شود.")
    add("stress_tolerance", by["stress_tolerance"]["value"] > 0.75,
        "تست زمان‌دار نزدیک امتحان برای تو مؤثر است.")
    add("reward_sensitivity", by["reward_sensitivity"]["value"] > 0.65,
        "نمایش سکه و استریک در داشبورد پررنگ بماند.")
    add("routine_preference", by["routine_preference"]["value"] > 0.65,
        "ساعت مطالعه ثابت و ترتیب تکراری درس‌ها حفظ شود.")
    add("novelty_preference", by["novelty_preference"]["value"] > 0.65,
        "در هر روز بین دو یا سه درس مختلف تنوع ایجاد شود.")
    add("self_criticism", by["self_criticism"]["value"] > 0.7,
        "گزارش‌ها روی پیشرفت نسبی تأکید کنند، نه فقط درصد خطا.")
    add("goal_orientation", by["goal_orientation"]["value"] > 0.7,
        "هدف هفتگی و شمارش معکوس امتحان برجسته شود.")
    add("discipline", by["discipline"]["value"] < 0.35,
        "یادآوری‌های کوتاه‌تر و بازه‌های کوچک‌تر مؤثرتر است.")
    return out
