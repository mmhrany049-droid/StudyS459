"""مصاحبهٔ برنامه‌ریزی ابتدای هفته — V2.1 (16_WEEKLY_PLANNING_INTERVIEW_V2_1).

۶ گروه سؤال: تعهدات ثابت، هدف، ظرفیت، وضعیت، محدودیت و ترجیح، بازنگری هفته قبل.
مصاحبه برنامه را قفل نمی‌کند؛ پاسخ‌ها فقط ورودی Planner هستند.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jalali import today_tehran, week_start_of
from app.models import PlanningInterview

INTERVIEW_GROUPS = [
    {
        "id": "commitments", "title": "تعهدات ثابت",
        "questions": [
            {"id": "busy_days", "text": "این هفته کدام روزها زمانت محدودتر است؟",
             "type": "days"},
            {"id": "special_event", "text": "کلاس، مدرسه، آزمون یا قرار مهم خاصی این هفته داری؟",
             "type": "text_or_none"},
            {"id": "routine_change", "text": "تغییری در برنامهٔ معمول این هفته داری؟",
             "type": "text_or_none"},
        ],
    },
    {
        "id": "goal", "title": "هدف",
        "questions": [
            {"id": "week_outcome", "text": "مهم‌ترین نتیجه‌ای که می‌خواهی آخر هفته داشته باشی چیست؟",
             "type": "text"},
            {"id": "priority_subject", "text": "کدام درس/موضوع بیشترین اولویت را دارد؟",
             "type": "subject"},
            {"id": "deadline", "text": "ددلاین خاصی وجود دارد؟", "type": "text_or_none"},
        ],
    },
    {
        "id": "capacity", "title": "ظرفیت",
        "questions": [
            {"id": "total_time", "text": "این هفته در مجموع چقدر وقت واقعی داری؟ (ساعت)",
             "type": "hours"},
            {"id": "high_energy_days", "text": "کدام روزها انرژی بیشتری داری؟", "type": "days"},
            {"id": "tired_day", "text": "کدام روز احتمال خستگی یا فشار بیشتر دارد؟", "type": "days"},
        ],
    },
    {
        "id": "state", "title": "وضعیت",
        "questions": [
            {"id": "sleep_state", "text": "خواب و انرژی فعلی‌ات چطور است؟", "type": "scale"},
            {"id": "stress_level", "text": "سطح استرس فعلی‌ات چقدر است؟", "type": "scale"},
            {"id": "mental_capacity", "text": "این هفته از نظر ذهنی چه ظرفیتی احساس می‌کنی؟",
             "type": "scale"},
        ],
    },
    {
        "id": "constraints", "title": "محدودیت و ترجیح",
        "questions": [
            {"id": "plan_style", "text": "برنامهٔ دقیق می‌خواهی یا انعطاف‌پذیر؟", "type": "choice",
             "options": ["دقیق", "انعطاف‌پذیر", "ترکیبی"]},
            {"id": "task_size", "text": "کارهای کوچک‌تر را ترجیح می‌دهی یا وعده‌های بزرگ‌تر؟",
             "type": "choice", "options": ["کارهای کوچک‌تر", "وعده‌های بزرگ‌تر", "بستگی دارد"]},
            {"id": "procrastination_risk", "text": "چه چیزی ممکن است این هفته باعث عقب‌انداختن کارها شود؟",
             "type": "text_or_none"},
        ],
    },
    {
        "id": "review", "title": "بازنگری هفته قبل",
        "questions": [
            {"id": "went_well", "text": "چه چیزی هفتهٔ قبل خوب پیش رفت؟", "type": "text_or_none"},
            {"id": "not_done", "text": "چه چیزی انجام نشد و چرا؟", "type": "text_or_none"},
            {"id": "load_feedback", "text": "برنامهٔ هفتهٔ قبل بیش از حد سنگین بود یا سبک؟",
             "type": "choice", "options": ["سنگین", "مناسب", "سبک"]},
        ],
    },
]

ALL_QUESTIONS = [q for g in INTERVIEW_GROUPS for q in g["questions"]]
QUESTION_IDS = {q["id"] for q in ALL_QUESTIONS}


def get_or_create(db: Session, user_id: int, week_start) -> PlanningInterview:
    iv = db.execute(
        select(PlanningInterview).where(
            PlanningInterview.user_id == user_id,
            PlanningInterview.week_start == week_start)
    ).scalar_one_or_none()
    if iv is None:
        iv = PlanningInterview(user_id=user_id, week_start=week_start,
                               answers_json=[], status="in_progress")
        db.add(iv)
        db.flush()
    return iv


def interview_view(db: Session, user: User, week_start) -> dict:
    iv = get_or_create(db, user.id, week_start)
    answered = {a["question_id"]: a for a in (iv.answers_json or [])}
    out_groups = []
    for g in INTERVIEW_GROUPS:
        qs = []
        for q in g["questions"]:
            item = dict(q)
            item["answer"] = answered.get(q["id"], {}).get("answer")
            item["answered"] = q["id"] in answered
            qs.append(item)
        out_groups.append({"id": g["id"], "title": g["title"], "questions": qs})
    return {
        "week_start": week_start.isoformat(),
        "status": iv.status,
        "groups": out_groups,
        "answered_count": len(answered),
        "total_count": len(ALL_QUESTIONS),
    }


def apply_answer(db: Session, user: User, week_start, question_id: str, answer) -> dict:
    if question_id not in QUESTION_IDS:
        return {"ok": False, "reason": "unknown_question"}
    iv = get_or_create(db, user.id, week_start)
    answers = list(iv.answers_json or [])
    answers = [a for a in answers if a["question_id"] != question_id]
    answers.append({"question_id": question_id, "answer": answer,
                    "answered_at": __import__("datetime").datetime.utcnow().isoformat()})
    iv.answers_json = answers
    return {"ok": True}


def complete(db: Session, user: User, week_start) -> dict:
    iv = get_or_create(db, user.id, week_start)
    iv.status = "completed"
    return {"ok": True, "answers": iv.answers_json}


def planner_inputs(db: Session, user: User, week_start) -> dict:
    """تبدیل پاسخ‌های مصاحبه به ورودی Planner."""
    iv = db.execute(
        select(PlanningInterview).where(
            PlanningInterview.user_id == user.id,
            PlanningInterview.week_start == week_start)
    ).scalar_one_or_none()
    if iv is None:
        return {"available": False}
    answers = {a["question_id"]: a.get("answer") for a in (iv.answers_json or [])}

    def days_list(v) -> list[int]:
        if not v:
            return []
        if isinstance(v, str):
            v = [v]
        mapping = {"sat": 0, "sun": 1, "mon": 2, "tue": 3, "wed": 4, "thu": 5, "fri": 6}
        return [mapping.get(x, x) if isinstance(x, str) else int(x) for x in v]

    return {
        "available": True,
        "completed": iv.status == "completed",
        "busy_days": days_list(answers.get("busy_days")),
        "high_energy_days": days_list(answers.get("high_energy_days")),
        "tired_days": days_list(answers.get("tired_day")),
        "priority_subject": answers.get("priority_subject"),
        "total_hours": answers.get("total_time"),
        "plan_style": answers.get("plan_style"),
        "task_size": answers.get("task_size"),
        "load_feedback": answers.get("load_feedback"),
        "procrastination_risk": answers.get("procrastination_risk"),
        "week_outcome": answers.get("week_outcome"),
    }
