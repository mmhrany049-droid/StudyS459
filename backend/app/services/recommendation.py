"""Recommendation engine — answers *WHAT to do*, after priority said *what matters*.

Every recommendation stores:

* the intervention type (chosen **before** any question is picked),
* human readable reasons (4 mandatory questions: What / Why / Evidence / What can I change),
* a duration range with confidence (never a fake precise number),
* a model version,
* the user's decision as data (accept / increase / decrease / reject / add another).
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import clamp, today_local
from ..db import models
from ..domain.enums import (
    INTERVENTION_LABELS_FA,
    InterventionType,
    RecommendationStatus,
)
from . import common, learning, priority, selection

MODEL_VERSION = config.MODEL_VERSION

INTERVENTION_QUESTION_MIX = {
    InterventionType.READ_LESSON: (0, 0),
    InterventionType.REVIEW: (8, 25),
    InterventionType.ACTIVE_RECALL: (6, 15),
    InterventionType.EASY_PRACTICE: (10, 20),
    InterventionType.MEDIUM_PRACTICE: (10, 25),
    InterventionType.DIFFICULT_PRACTICE: (8, 18),
    InterventionType.MIXED_PRACTICE: (12, 25),
    InterventionType.TIMED_QUIZ: (10, 20),
    InterventionType.DIAGNOSTIC: (6, 12),
    InterventionType.MOCK_EXAM: (20, 40),
    InterventionType.PREREQUISITE_REVIEW: (8, 20),
    InterventionType.ERROR_REVIEW: (8, 25),
}


def choose_intervention(
    db: Session,
    user: models.User,
    topic_id: int,
    *,
    taught: Optional[bool] = None,
    exam_days: Optional[int] = None,
    prerequisite_weak: bool = False,
) -> dict:
    """First decide WHY/WHAT KIND of intervention, then questions later."""
    state = db.scalars(
        select(models.LearningState).where(
            models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
        )
    ).first()
    if taught is None:
        row = db.scalars(
            select(models.TaughtTopic).where(
                models.TaughtTopic.user_id == user.id, models.TaughtTopic.topic_id == topic_id
            )
        ).first()
        taught = bool(row and row.taught)

    reasons: list[str] = []
    if not taught:
        reasons.append("این مبحث هنوز «تدرس‌شده» علامت نخورده؛ تمرین قبل از تدریس توصیه نمی‌شود.")
        return {"intervention": InterventionType.READ_LESSON.value, "reasons": reasons, "confidence": 0.7}

    if state is None or not state.answered:
        reasons.append("هیچ شواهدی از این مبحث نداریم؛ یک تشخیص کوتاه کم‌هزینه‌تر از تمرین زیاد است.")
        return {"intervention": InterventionType.DIAGNOSTIC.value, "reasons": reasons, "confidence": 0.5}

    if prerequisite_weak or (state.prerequisite_health is not None and state.prerequisite_health < 0.4):
        reasons.append("پیش‌نیاز این مبحث ضعیف است؛ ابتدا پیش‌نیاز مرور می‌شود.")
        return {"intervention": InterventionType.PREREQUISITE_REVIEW.value, "reasons": reasons, "confidence": state.confidence or 0.4}

    uncertainty = state.uncertainty if state.uncertainty is not None else 1.0
    if uncertainty > config.value("recommendation.diagnostic_uncertainty_threshold"):
        reasons.append(
            f"اطمینان تخمین ما {round((1 - uncertainty) * 100)}٪ است؛ تشخیص کوتاه اطلاعات بیشتری تولید می‌کند."
        )
        return {"intervention": InterventionType.DIAGNOSTIC.value, "reasons": reasons, "confidence": state.confidence or 0.3}

    if state.repeated_error_signal and state.repeated_error_signal >= 0.25:
        reasons.append("الگوی خطای تکرارشونده در این مبحث دیده شده؛ بازبینی خطاها اولویت دارد.")
        return {"intervention": InterventionType.ERROR_REVIEW.value, "reasons": reasons, "confidence": state.confidence or 0.5}

    if state.retention_estimate is not None and state.retention_estimate < 0.6 and state.answered >= 5:
        reasons.append(
            f"تخمین نگه‌داشت {round(state.retention_estimate * 100)}٪ است؛ مرور فعال از تمرین جدید مفیدتر است."
        )
        return {"intervention": InterventionType.ACTIVE_RECALL.value, "reasons": reasons, "confidence": state.confidence or 0.4}

    coverage = state.coverage if state.coverage is not None else None
    accuracy = state.accuracy if state.accuracy is not None else None
    if exam_days is not None and exam_days <= 10 and coverage is not None and coverage > 0.4:
        reasons.append(f"{exam_days} روز تا امتحان مرتبط باقی است؛ تمرین زمان‌دار انتخاب شد.")
        return {"intervention": InterventionType.TIMED_QUIZ.value, "reasons": reasons, "confidence": 0.5}

    if coverage is not None and coverage < config.value("priority.low_coverage_threshold"):
        if accuracy is not None and accuracy >= config.value("priority.high_accuracy_threshold"):
            reasons.append("پوشش پایین اما دقت خوب؛ دامنه سؤالات باید گسترده‌تر شود (تمرین متوسط جدید).")
            return {"intervention": InterventionType.MEDIUM_PRACTICE.value, "reasons": reasons, "confidence": state.confidence or 0.4}
        reasons.append("پوشش پایین است؛ تمرین در سطح آسان/متوسط برای پوشش بیشتر توصیه می‌شود.")
        return {"intervention": InterventionType.EASY_PRACTICE.value, "reasons": reasons, "confidence": state.confidence or 0.4}

    if accuracy is not None and accuracy < config.value("priority.weak_accuracy_threshold"):
        reasons.append(f"دقت {round(accuracy * 100)}٪ پایین‌تر از آستانه است؛ تمرین متوسط با بازبینی خطا.")
        return {"intervention": InterventionType.MEDIUM_PRACTICE.value, "reasons": reasons, "confidence": state.confidence or 0.4}

    reasons.append("عملکرد در سطوح پایین‌تر خوب بوده؛ وقت رفتن به سؤالات دشوارتر است.")
    return {"intervention": InterventionType.DIFFICULT_PRACTICE.value, "reasons": reasons, "confidence": state.confidence or 0.5}


def question_count_for(intervention: str) -> int:
    low, high = INTERVENTION_QUESTION_MIX.get(
        InterventionType(intervention), (config.value("recommendation.min_question_count"), config.value("recommendation.max_question_count"))
    )
    if high <= low:
        return low
    midpoint = (low + high) // 2
    return max(1, midpoint)


def build_recommendation(
    db: Session,
    user: models.User,
    *,
    topic_id: int,
    scope: str = "weekly",
    day: Optional[_dt.date] = None,
    exam_days: Optional[int] = None,
    forced_intervention: Optional[str] = None,
    priority_item: Optional[dict] = None,
    quiet: bool = True,
) -> models.Recommendation:
    day = day or today_local()
    priority_item = priority_item or priority.compute_topic_priority(db, user, topic_id, day=day)
    decision = choose_intervention(
        db,
        user,
        topic_id,
        exam_days=exam_days,
        prerequisite_weak=bool(
            (priority_item["components"]["prerequisite_need"]["value"] or 0) > 0.5
        ),
    )
    intervention = forced_intervention or decision["intervention"]
    count = question_count_for(intervention)
    selection_preview = selection.select_for_intervention(
        db, user, topic_id=topic_id, intervention=intervention, count=count
    )
    from . import duration as duration_service

    estimate = duration_service.estimate_for_task(
        db,
        user,
        task_type="test_session",
        question_count=selection_preview["count"] or None,
        topic_id=topic_id,
        intervention=intervention,
    )
    topic = db.get(models.Topic, topic_id)
    reasons = [
        {"code": "priority", "weight": priority_item["score"],
         "human_text": f"امتیاز اولویت این مبحث {round(priority_item['score'], 3)} است.",
         "evidence": {r["component"]: r["contribution"] for r in priority_item["top_reasons"]}},
        {"code": "intervention", "weight": None,
         "human_text": " / ".join(decision["reasons"]),
         "evidence": {"intervention": intervention}},
    ]
    if selection_preview["reasons"]:
        reasons.append(
            {"code": "selection", "weight": None, "human_text": " ".join(selection_preview["reasons"]), "evidence": selection_preview["mix"]}
        )
    reasons.append(
        {
            "code": "duration",
            "weight": estimate["confidence"],
            "human_text": f"برآورد زمان: {estimate['label']} (اطمینان {estimate['confidence_band']}).",
            "evidence": estimate["based_on"],
        }
    )
    for component in priority_item["top_reasons"][:2]:
        reasons.append(
            {
                "code": f"component.{component['component']}",
                "weight": component["contribution"],
                "human_text": f"{component['label']}: {component['evidence'].get('reason', '')}",
                "evidence": component["evidence"],
            }
        )

    title = f"{INTERVENTION_LABELS_FA.get(InterventionType(intervention), intervention)} — {topic.title if topic else ''}".strip()
    human_reason = decision["reasons"][0] if decision["reasons"] else "بر پایه وضعیت یادگیری و اولویت این هفته."
    recommendation = models.Recommendation(
        user_id=user.id,
        scope=scope,
        intervention_type=intervention,
        book_id=topic.book_id if topic else None,
        topic_id=topic_id,
        title=title,
        human_reason=human_reason,
        question_count=selection_preview["count"] or None,
        duration_low=estimate["low_minutes"],
        duration_high=estimate["high_minutes"],
        priority_score=priority_item["score"],
        confidence=estimate["confidence"],
        recommended_for=day,
        quiet=quiet,
        explanation={
            "what": title,
            "why": human_reason,
            "evidence": {
                "priority_components": priority_item["components"],
                "priority_contributions": priority_item["top_reasons"],
                "selection_mix": selection_preview["mix"],
                "duration_method": estimate["method"],
            },
            "what_can_i_change": [
                "می‌توانی تعداد سؤال یا روز انجام را تغییر بدهی (ثبت دستی).",
                "می‌توانی این پیشنهاد را رد کنی؛ رد شدن در آینده به‌عنوان شواهد استفاده می‌شود، نه خطا.",
                "می‌توانی نوع مداخله را عوض کنی (مثلاً از تمرین دشوار به مرور).",
            ],
            "confidence": estimate["confidence"],
            "model_version": MODEL_VERSION,
        },
        model_version=MODEL_VERSION,
    )
    db.add(recommendation)
    db.flush()
    for reason in reasons:
        db.add(
            models.RecommendationReason(
                recommendation_id=recommendation.id,
                code=reason["code"],
                weight=reason["weight"],
                human_text=reason["human_text"],
                evidence=reason["evidence"],
            )
        )
    db.flush()
    return recommendation


def weekly_suggestions(
    db: Session, user: models.User, *, limit: Optional[int] = None, day: Optional[_dt.date] = None
) -> list[dict]:
    """'These topics deserve more attention this week' — before weekly planning."""
    day = day or today_local()
    limit = limit or config.value("recommendation.max_suggestions_per_day")
    items = priority.compute_priorities(db, user, horizon="week", day=day, limit=limit * 3)
    suggestions = []
    for item in items:
        taught_row = db.scalars(
            select(models.TaughtTopic).where(
                models.TaughtTopic.user_id == user.id, models.TaughtTopic.topic_id == item["topic_id"]
            )
        ).first()
        decision = choose_intervention(db, user, item["topic_id"], taught=bool(taught_row and taught_row.taught))
        suggestions.append(
            {
                "topic_id": item["topic_id"],
                "topic_title": item["topic_title"],
                "book_id": db.get(models.Topic, item["topic_id"]).book_id if db.get(models.Topic, item["topic_id"]) else None,
                "score": item["score"],
                "confidence": item["confidence"],
                "taught": bool(taught_row and taught_row.taught),
                "suggested_intervention": decision["intervention"],
                "suggested_intervention_label": INTERVENTION_LABELS_FA.get(
                    InterventionType(decision["intervention"]), decision["intervention"]
                ),
                "short_reason": _short_reason(item, decision),
                "why": priority.explain_priority(item),
                "priority_components": item["components"],
                "top_reasons": item["top_reasons"],
            }
        )
        if len(suggestions) >= limit:
            break
    return suggestions


def _short_reason(item: dict, decision: dict) -> str:
    """Quiet suggestion engine: a short human sentence, never a weight dump."""
    top = item["top_reasons"][0] if item["top_reasons"] else None
    if top is None:
        return "این مبحث در محاسبه اولویت این هفته بالاتر آمد."
    mapping = {
        "exam_need": "امتحان نزدیکی این مبحث را پوشش می‌دهد",
        "goal_need": "از هدف سه‌ماهه‌ات عقب‌تر از برنامه است",
        "learning_need": "دقت یا اطمینان کافی در این مبحث نداریم",
        "coverage_need": "بخش زیادی از سؤالات این مبحث دیده نشده",
        "review_need": "سؤالات غلط/نزده باز در صف مرور دارد",
        "prerequisite_need": "پیش‌نیازش ضعیف است",
        "retention_risk": "احتمال فراموشی‌اش بالا رفته",
        "behavioral_fit": "با وضعیت فعلی تو جور است",
        "opportunity": "ظرفیت امروز برای این کار جا دارد",
        "capacity_cost": "هزینه زمانی‌اش را هم در نظر گرفتیم",
        "recent_saturation": "اخیراً زیاد رویش کار کرده‌ای",
    }
    return mapping.get(top["component"], "در محاسبه اولویت این هفته بالا آمد")


def record_feedback(
    db: Session,
    user: models.User,
    recommendation_id: int,
    action: str,
    *,
    payload: Optional[dict] = None,
) -> dict:
    """Accept / Increase / Decrease / Reject / Add another — stored as data."""
    recommendation = db.get(models.Recommendation, recommendation_id)
    if not recommendation or recommendation.user_id != user.id:
        from ..core.errors import NotFoundError

        raise NotFoundError("پیشنهاد پیدا نشد.")
    payload = payload or {}
    mapping = {
        "accept": RecommendationStatus.ACCEPTED,
        "increase": RecommendationStatus.INCREASED,
        "decrease": RecommendationStatus.DECREASED,
        "reject": RecommendationStatus.REJECTED,
        "adjust": RecommendationStatus.ACCEPTED,
    }
    if action not in mapping:
        from ..core.errors import ValidationError

        raise ValidationError("عملیات نامعتبر است. مقادیر مجاز: accept, increase, decrease, reject, adjust")
    before = {
        "status": recommendation.status,
        "question_count": recommendation.question_count,
        "duration_low": recommendation.duration_low,
        "duration_high": recommendation.duration_high,
    }
    if action == "increase":
        recommendation.question_count = int((recommendation.question_count or 10) * 1.25)
    elif action == "decrease":
        recommendation.question_count = max(4, int((recommendation.question_count or 10) * 0.75))
    elif action == "adjust":
        if payload.get("question_count"):
            recommendation.question_count = int(payload["question_count"])
        if payload.get("intervention_type"):
            recommendation.intervention_type = payload["intervention_type"]
        if payload.get("recommended_for"):
            recommendation.recommended_for = common.parse_date_if_string(payload["recommended_for"])
    recommendation.status = mapping[action].value
    recommendation.feedback = {
        **(recommendation.feedback or {}),
        action: {
            "at": common.jdatetime(_now()),
            "note": payload.get("note"),
            "reason": payload.get("reason"),
        },
    }
    db.flush()
    common.audit(
        db, "recommendation_feedback", user_id=user.id, entity_type="recommendation", entity_id=recommendation_id,
        reason=action, before=before, after={"status": recommendation.status},
    )
    common.observe(
        db, user.id, "recommendation_feedback",
        payload={"recommendation_id": recommendation_id, "action": action, "topic_id": recommendation.topic_id},
        source="user",
    )
    # feedback is evidence, never a "quality proof"; it only tunes future ranking
    if action in {"reject", "decrease"}:
        keep = config.value("recommendation.accept_feedback_weight")
        snapshot = db.scalars(
            select(models.PrioritySnapshot).where(
                models.PrioritySnapshot.user_id == user.id,
                models.PrioritySnapshot.topic_id == recommendation.topic_id,
                models.PrioritySnapshot.horizon == "week",
            )
        ).first()
        if snapshot and snapshot.score is not None:
            snapshot.components = {
                **(snapshot.components or {}),
                "user_feedback": {"action": action, "applied_weight": keep, "note": "بازخورد کاربر شواهد است، نه خطا"},
            }
    return {
        "recommendation_id": recommendation_id,
        "status": recommendation.status,
        "question_count": recommendation.question_count,
        "note": "بازخورد کاربر به‌عنوان «شواهد» ذخیره شد و Planner بدون اجازه چیزی را overwrite نمی‌کند.",
    }


def _now():
    from ..core.timeutil import now_utc

    return now_utc()


def convert_to_task(db: Session, user: models.User, recommendation: models.Recommendation, *, day: _dt.date, minutes: Optional[int] = None):
    from . import tasks as tasks_service

    topic = db.get(models.Topic, recommendation.topic_id) if recommendation.topic_id else None
    estimate_minutes = minutes or int(round(((recommendation.duration_low or 60) + (recommendation.duration_high or 90)) / 2))
    task = tasks_service.create_task(
        db,
        user,
        {
            "title": recommendation.title or "کار پیشنهادی",
            "task_type": "test_session" if recommendation.intervention_type != InterventionType.READ_LESSON.value else "read_lesson",
            "intervention_type": recommendation.intervention_type,
            "book_id": recommendation.book_id,
            "topic_id": recommendation.topic_id,
            "planned_date": day,
            "planned_question_count": recommendation.question_count,
            "planned_minutes": estimate_minutes,
            "duration_low": recommendation.duration_low,
            "duration_high": recommendation.duration_high,
            "duration_confidence": recommendation.confidence,
            "source": "planner",
            "recommendation_id": recommendation.id,
            "evidence": {"recommendation_explanation": recommendation.explanation},
        },
    )
    recommendation.status = RecommendationStatus.CONVERTED.value
    db.flush()
    return task


def quiet_suggestions(db: Session, user: models.User, *, day: Optional[_dt.date] = None) -> list[dict]:
    """Quiet suggestion engine (V2.2): at most one card per day, short reason,
    dismissable for 24h, package size capped, never nagging."""
    day = day or today_local()
    cap = config.value("recommendation.quiet_max_per_day")
    dismissed = list(
        db.scalars(
            select(models.Notification).where(
                models.Notification.user_id == user.id,
                models.Notification.dismissed_until.is_not(None),
                models.Notification.dismissed_until > _now(),
            )
        )
    )
    if len(dismissed) >= cap:
        return []
    suggestions = []
    # 1) nearest exam topics
    exam_suggestions = exam_readiness_suggestions(db, user, day=day, limit=1)
    suggestions.extend(exam_suggestions[:cap])
    if len(suggestions) < cap:
        # 2) taught recently, never practised
        gap = taught_without_practice(db, user, limit=cap - len(suggestions))
        suggestions.extend(gap)
    if len(suggestions) < cap:
        # 3) ordinary review queue
        stats = db.execute(
            select(models.ReviewItem.priority, models.ReviewItem.topic_id)
            .where(models.ReviewItem.user_id == user.id, models.ReviewItem.state == "open")
            .limit(50)
        ).all()
        if stats:
            critical = [row for row in stats if row[0] == "critical"]
            topic_id = (critical or stats)[0][1]
            if topic_id:
                topic = db.get(models.Topic, topic_id)
                suggestions.append(
                    {
                        "kind": "review_queue",
                        "topic_id": topic_id,
                        "topic_title": topic.title if topic else None,
                        "questions": min(
                            config.value("recommendation.package_max_questions"),
                            max(config.value("recommendation.package_min_questions"), len(stats)),
                        ),
                        "short_reason": f"{len(stats)} سؤال در صف مرور داری؛ {'بحرانی‌ها' if critical else 'قدیمی‌ترها'} جلوترند.",
                        "actions": ["add_today", "later", "dismiss"],
                    }
                )
    for suggestion in suggestions:
        suggestion.setdefault("actions", ["add_today", "later", "dismiss"])
        suggestion["quiet"] = True
    return suggestions[:cap]


def exam_readiness_suggestions(
    db: Session, user: models.User, *, day: Optional[_dt.date] = None, limit: int = 2
) -> list[dict]:
    day = day or today_local()
    exams = list(
        db.scalars(
            select(models.Exam).where(
                models.Exam.user_id == user.id,
                models.Exam.status.in_(["planned", "in_progress"]),
                models.Exam.exam_date >= day,
            ).order_by(models.Exam.exam_date)
        )
    )
    results = []
    for exam in exams:
        marks = list(
            db.scalars(
                select(models.ExamTopic).where(
                    models.ExamTopic.exam_id == exam.id,
                    models.ExamTopic.checked.is_(True),
                )
            )
        )
        if not marks:
            continue
        preferred_kind = "actual" if any(m.mark_kind == "actual" for m in marks) else "planned"
        topic_ids = [m.topic_id for m in marks if m.mark_kind == preferred_kind] or [m.topic_id for m in marks]
        weak_topics = []
        for topic_id in topic_ids:
            state = db.scalars(
                select(models.LearningState).where(
                    models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
                )
            ).first()
            priority_item = priority.compute_topic_priority(db, user, topic_id, day=day)
            coverage = state.coverage if state and state.coverage is not None else 0.0
            accuracy = state.accuracy if state and state.accuracy is not None else 0.0
            open_review = db.scalar(
                select(func.count(models.ReviewItem.id)).where(
                    models.ReviewItem.user_id == user.id,
                    models.ReviewItem.topic_id == topic_id,
                    models.ReviewItem.state == "open",
                )
            )
            need = (1 - coverage) * 0.5 + (1 - accuracy) * 0.3 + min(1.0, (open_review or 0) / 10) * 0.2
            weak_topics.append(
                {
                    "topic_id": topic_id,
                    "topic_title": db.get(models.Topic, topic_id).title if db.get(models.Topic, topic_id) else None,
                    "coverage": coverage,
                    "accuracy": accuracy,
                    "open_review": open_review or 0,
                    "need": round(need, 3),
                    "priority_score": priority_item["score"],
                }
            )
        weak_topics.sort(key=lambda item: item["need"] + item["priority_score"], reverse=True)
        weakest = weak_topics[:3]
        if not weakest:
            continue
        questions = min(
            config.value("recommendation.package_max_questions"),
            max(config.value("recommendation.package_min_questions"), 5 * len(weakest)),
        )
        days_left = (exam.exam_date - day).days
        results.append(
            {
                "kind": "exam_readiness",
                "exam_id": exam.id,
                "exam_title": exam.title,
                "exam_date": common.jdate(exam.exam_date),
                "days_left": days_left,
                "topic_count": len(topic_ids),
                "weakest_topics": weakest,
                "questions": questions,
                "short_reason": (
                    f"برای «{exam.title}» ({days_left} روز مانده) {len(weakest)} مبحث پوشش/دقت پایین‌تری دارند — "
                    f"{questions} تست پیشنهاد می‌شود."
                ),
                "actions": ["add_today", "later", "dismiss"],
                "quiet": True,
            }
        )
        if len(results) >= limit:
            break
    return results


def taught_without_practice(db: Session, user: models.User, *, limit: int = 1) -> list[dict]:
    rows = list(
        db.scalars(
            select(models.TaughtTopic)
            .where(models.TaughtTopic.user_id == user.id, models.TaughtTopic.taught.is_(True))
            .order_by(models.TaughtTopic.taught_at.desc())
        )
    )
    results = []
    for row in rows:
        attempts = db.scalar(
            select(func.count(models.AttemptResult.id)).where(
                models.AttemptResult.user_id == user.id, models.AttemptResult.topic_id == row.topic_id
            )
        ) or 0
        if attempts:
            continue
        topic = db.get(models.Topic, row.topic_id)
        if not topic:
            continue
        pool = db.scalar(
            select(func.count(models.Question.id)).where(
                models.Question.primary_topic_id == row.topic_id, models.Question.active.is_(True)
            )
        ) or 0
        if pool == 0:
            continue
        results.append(
            {
                "kind": "taught_no_practice",
                "topic_id": row.topic_id,
                "topic_title": topic.title,
                "questions": min(15, max(10, pool // 2)),
                "short_reason": f"«{topic.title}» تدریس‌شده علامت خورده ولی هنوز تمرینی از آن ثبت نشده.",
                "actions": ["add_today", "later", "dismiss"],
                "quiet": True,
            }
        )
        if len(results) >= limit:
            break
    return results


def generate_recommendations(
    db: Session,
    user: models.User,
    *,
    day: Optional[_dt.date] = None,
    limit: Optional[int] = None,
    scope: str = "weekly",
) -> list[models.Recommendation]:
    """Persist recommendations for the topics that currently matter most.

    Idempotent: a topic that already has an open recommendation is not
    duplicated, so repeated calls never flood the user with copies.
    """
    day = day or today_local()
    limit = limit or config.value("recommendation.max_suggestions_per_day")
    items = priority.compute_priorities(db, user, horizon="week", day=day, limit=limit * 2)
    open_topics = set(
        db.scalars(
            select(models.Recommendation.topic_id).where(
                models.Recommendation.user_id == user.id,
                models.Recommendation.status.in_(["suggested", "accepted", "planned"]),
            )
        )
    )
    created: list[models.Recommendation] = []
    for item in items:
        if len(created) >= limit:
            break
        topic_id = common.to_int(item.get("topic_id"))
        if not topic_id or topic_id in open_topics:
            continue
        exam_days = item.get("exam_days")
        row = build_recommendation(
            db,
            user,
            topic_id=topic_id,
            scope=scope,
            day=day,
            exam_days=exam_days,
            priority_item=item,
        )
        created.append(row)
        open_topics.add(topic_id)
    return created


def list_recommendations(db: Session, user: models.User, *, status: Optional[str] = None, limit: int = 50) -> list[dict]:
    stmt = select(models.Recommendation).where(models.Recommendation.user_id == user.id)
    if status:
        stmt = stmt.where(models.Recommendation.status == status)
    rows = list(db.scalars(stmt.order_by(models.Recommendation.id.desc()).limit(limit)))
    topic_titles = {
        topic.id: topic.title
        for topic in db.scalars(select(models.Topic).where(models.Topic.id.in_([r.topic_id for r in rows if r.topic_id] or [0])))
    }
    return [
        {
            "id": row.id,
            "title": row.title,
            "topic_id": row.topic_id,
            "topic_title": topic_titles.get(row.topic_id),
            "scope": row.scope,
            "intervention_type": row.intervention_type,
            "status": row.status,
            "priority_score": row.priority_score,
            "confidence": row.confidence,
            "question_count": row.question_count,
            "duration_low": row.duration_low,
            "duration_high": row.duration_high,
            "duration_label": f"{row.duration_low} تا {row.duration_high} دقیقه" if row.duration_low else None,
            "recommended_for": common.jdate(row.recommended_for),
            "human_reason": row.human_reason,
        }
        for row in rows
    ]


def explanation(db: Session, recommendation_id: int) -> dict:
    recommendation = db.get(models.Recommendation, recommendation_id)
    if not recommendation:
        from ..core.errors import NotFoundError

        raise NotFoundError("پیشنهاد پیدا نشد.")
    reasons = list(
        db.scalars(
            select(models.RecommendationReason).where(
                models.RecommendationReason.recommendation_id == recommendation_id
            )
        )
    )
    topic = db.get(models.Topic, recommendation.topic_id) if recommendation.topic_id else None
    return {
        "recommendation_id": recommendation_id,
        "what": recommendation.title,
        "topic": {"id": topic.id, "title": topic.title} if topic else None,
        "why": recommendation.human_reason,
        "reasons": [
            {
                "code": reason.code,
                "weight": reason.weight,
                "text": reason.human_text,
                "evidence": reason.evidence,
            }
            for reason in reasons
        ],
        "evidence": (recommendation.explanation or {}).get("evidence", {}),
        "what_can_i_change": (recommendation.explanation or {}).get("what_can_i_change", []),
        "confidence": recommendation.confidence,
        "confidence_band": common.confidence_band(recommendation.confidence),
        "model_version": recommendation.model_version,
        "disclaimer": "هیچ توصیه‌ای با عبارت «هوش مصنوعی گفته» توضیح داده نمی‌شود؛ دلیل و شواهد باید قابل بررسی باشند.",
    }
