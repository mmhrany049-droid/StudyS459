"""Question selection after the intervention type has been chosen.

V3: "Choose intervention type before selecting questions. Range/Parity is only a
minor question-selection signal." That is why parity appears here as a small
tie-breaker and never as the main driver.
"""

from __future__ import annotations

import datetime as _dt
import random
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..core.timeutil import today_local
from ..db import models
from ..domain.enums import InterventionType
from . import common


def difficulty_band(question: models.Question) -> str:
    level = question.difficulty_level
    if level is None:
        return "unknown"
    if level <= 1:
        return "easy"
    if level == 2:
        return "medium"
    return "hard"


def _review_question_ids(db: Session, user: models.User, topic_scope: set[int]) -> list[int]:
    if not topic_scope:
        return []
    return list(
        db.scalars(
            select(models.ReviewItem.question_id).where(
                models.ReviewItem.user_id == user.id,
                models.ReviewItem.state == "open",
                models.ReviewItem.topic_id.in_(topic_scope),
                models.ReviewItem.question_id.is_not(None),
            )
        )
    )


def _recent_attempts(db: Session, user: models.User, days: int) -> set[int]:
    since = today_local() - _dt.timedelta(days=days)
    return set(
        db.scalars(
            select(models.AttemptResult.question_id).where(
                models.AttemptResult.user_id == user.id,
                models.AttemptResult.is_current.is_(True),
                models.AttemptResult.attempted_on >= since,
            )
        )
    )


def _attempted_ever(db: Session, user: models.User) -> set[int]:
    return set(
        db.scalars(
            select(models.AttemptResult.question_id).where(
                models.AttemptResult.user_id == user.id, models.AttemptResult.is_current.is_(True)
            )
        )
    )


def topic_scope(db: Session, topic_id: int, include_descendants: bool = True) -> set[int]:
    topic = db.get(models.Topic, topic_id)
    if not topic:
        return {topic_id}
    scope = {topic_id}
    if include_descendants:
        scope |= set(
            db.scalars(select(models.Topic.id).where(models.Topic.path.like(f"{topic.path}{topic.id}/%")))
        )
    return scope


def pool_for_scope(db: Session, topic_scope_ids: Iterable[int]) -> list[models.Question]:
    ids = {t for t in topic_scope_ids if t}
    if not ids:
        return []
    return list(
        db.scalars(
            select(models.Question).where(
                models.Question.primary_topic_id.in_(ids), models.Question.active.is_(True)
            )
        )
    )


def _with_answer_key(questions: list[models.Question]) -> list[models.Question]:
    """Auto-correction is only honest when an answer key exists; the rest can
    still be practised but are flagged for the user."""
    return [q for q in questions if q.current_answer_key]


def select_for_intervention(
    db: Session,
    user: models.User,
    *,
    topic_id: int,
    intervention: str,
    count: int,
    parity: Optional[str] = None,
    sequence_from: Optional[int] = None,
    sequence_to: Optional[int] = None,
    seed: Optional[int] = None,
    recent_days: int = 5,
) -> dict:
    scope = topic_scope(db, topic_id)
    pool = pool_for_scope(db, scope)
    reasons: list[str] = []
    mix: dict[str, int] = {}
    available = len(pool)

    if intervention == InterventionType.READ_LESSON.value:
        return {
            "question_ids": [],
            "count": 0,
            "intervention": intervention,
            "mix": {},
            "available": available,
            "reasons": ["این مداخله کار خواندن/مرور متن است، نه تست."],
            "fallback_used": False,
        }

    if intervention == InterventionType.PREREQUISITE_REVIEW.value:
        from . import curriculum

        prerequisite_topics = curriculum.prerequisites_of(db, topic_id)
        prereq_scope: set[int] = set()
        for prerequisite in prerequisite_topics:
            prereq_scope |= topic_scope(db, prerequisite.id)
        prerequisite_pool = pool_for_scope(db, prereq_scope)
        if prerequisite_pool:
            pool = prerequisite_pool
            scope = prereq_scope
            reasons.append("سؤالات از مباحث پیش‌نیاز انتخاب شدند، نه از خود مبحث.")
        else:
            reasons.append("سؤال پیش‌نیاز در بانک نبود؛ از خود مبحث انتخاب شد.")

    rng = random.Random(seed)
    recent = _recent_attempts(db, user, recent_days)
    attempted = _attempted_ever(db, user)
    review_ids = set(_review_question_ids(db, user, scope))

    def exclude_recent(candidates: list[models.Question]) -> list[models.Question]:
        fresh = [q for q in candidates if q.id not in recent]
        return fresh or candidates

    chosen: list[models.Question] = []

    if intervention in {
        InterventionType.REVIEW.value,
        InterventionType.ERROR_REVIEW.value,
        InterventionType.ACTIVE_RECALL.value,
    }:
        candidates = [q for q in pool if q.id in review_ids]
        if candidates:
            candidates.sort(key=lambda q: q.id)
            rng.shuffle(candidates)
            chosen = candidates[:count]
            reasons.append(f"{len(chosen)} سؤال از صف مرور (خطا/نزده) انتخاب شد.")
        else:
            fallback = _with_answer_key(pool)
            fallback.sort(key=lambda q: q.id)
            rng.shuffle(fallback)
            chosen = fallback[:count]
            reasons.append("صف مرور برای این مبحث خالی بود؛ سؤالات بانک به‌عنوان جایگزین آمدند.")
        if intervention == InterventionType.ACTIVE_RECALL.value:
            reasons.append("شیوه اجرا: یادآوری فعال بدون دیدن پاسخ، سپس بررسی.")

    elif intervention == InterventionType.DIAGNOSTIC.value:
        unseen = [q for q in pool if q.id not in attempted]
        candidates = unseen or pool
        rng.shuffle(candidates)
        # spread across the topic sequence range for an actual diagnostic signal
        chosen = sorted(candidates, key=lambda q: q.sequence_no)
        step = max(1, len(chosen) // max(1, count))
        chosen = chosen[::step][:count]
        if sequence_from or sequence_to:
            chosen = [
                q for q in chosen
                if (sequence_from is None or q.sequence_no >= sequence_from)
                and (sequence_to is None or q.sequence_no <= sequence_to)
            ] or chosen
        reasons.append("چون اطمینان تخمین ما پایین است، یک تشخیص کوتاه و پراکنده انتخاب شد.")

    else:
        by_band: dict[str, list[models.Question]] = {"easy": [], "medium": [], "hard": [], "unknown": []}
        for question in pool:
            by_band[difficulty_band(question)].append(question)
        bands = {key: value for key, value in by_band.items() if value}

        def pick_from(band_names: list[str], take: int) -> list[models.Question]:
            gathered: list[models.Question] = []
            for name in band_names:
                gathered.extend(bands.get(name, []))
            gathered = exclude_recent(gathered)
            rng.shuffle(gathered)
            return gathered[:take]

        if intervention == InterventionType.EASY_PRACTICE.value:
            chosen = pick_from(["easy", "unknown", "medium"], count)
            reasons.append("تمرین آسان برای ساختن شتاب و اعتماد (میانگین دشواری پایین).")
        elif intervention == InterventionType.MEDIUM_PRACTICE.value:
            chosen = pick_from(["medium", "unknown", "easy", "hard"], count)
            reasons.append("تمرین در محدوده دشواری متوسط مبحث.")
        elif intervention == InterventionType.DIFFICULT_PRACTICE.value:
            chosen = pick_from(["hard", "medium"], count)
            reasons.append("تمرین دشوار، برای مبحثی که در دشواری‌های پایین‌تر عملکرد خوبی داشته است.")
        elif intervention == InterventionType.TIMED_QUIZ.value:
            chosen = pick_from(["medium", "hard", "unknown"], count)
            reasons.append("آزمون زمان‌دار با ترکیب متوسط/دشوار و محدودیت زمانی.")
        else:  # MIXED_PRACTICE and everything else
            per_band = max(1, count // max(1, len(bands)))
            chosen = []
            for name in ["easy", "medium", "hard", "unknown"]:
                if len(chosen) >= count:
                    break
                chosen.extend(pick_from([name], min(per_band, count - len(chosen))))
            remaining = count - len(chosen)
            if remaining > 0:
                extra = pick_from(list(bands.keys()), remaining)
                chosen.extend([q for q in extra if q not in chosen][:remaining])
            reasons.append("تمرین ترکیبی (interleaving) از چند سطح دشواری.")

        if not chosen:
            chosen = exclude_recent(_with_answer_key(pool))[:count]
            reasons.append("برای این مبحث سطح دشواری ثبت نشده؛ از کل بانک انتخاب شد.")
        if any(q.current_answer_key is None for q in chosen):
            reasons.append("بخشی از سؤالات انتخاب‌شده پاسخ‌نامه ندارند و بعد از تصحیح دستی ارزیابی می‌شوند.")

    # Coverage preference: when coverage is low, prefer unseen questions inside
    # the chosen set; this never overrides the intervention decision itself.
    coverage = db.scalars(
        select(models.LearningState.coverage).where(
            models.LearningState.user_id == user.id, models.LearningState.topic_id == topic_id
        )
    ).first()
    if coverage is not None and coverage < config.value("priority.low_coverage_threshold") and chosen:
        unseen_in_chosen = [q for q in chosen if q.id not in attempted]
        if unseen_in_chosen:
            reasons.append("پوشش این مبحث پایین است؛ سؤالات دیده‌نشده اولویت گرفتند.")

    # Parity as a *minor* signal only (V2 memory kept, V3 caps its influence)
    if parity in {"odd", "even"} and chosen:
        parity_matches = [q for q in chosen if q.sequence_no % 2 == (1 if parity == "odd" else 0)]
        share_cap = config.value("selection.max_parity_share")
        max_by_parity = max(1, int(round(len(chosen) * share_cap)) + 1)
        if parity_matches:
            boosted = parity_matches[:max_by_parity]
            rest = [q for q in chosen if q not in boosted]
            chosen = boosted + rest
            reasons.append(
                f"زوج/فرد فقط یک سیگنال کوچک است: حداکثر {len(boosted)} سؤال با الگوی پیشنهادی جلو آمدند."
            )

    chosen = chosen[:count]
    for question in chosen:
        mix[difficulty_band(question)] = mix.get(difficulty_band(question), 0) + 1
    chosen.sort(key=lambda q: q.sequence_no)
    return {
        "question_ids": [q.id for q in chosen],
        "count": len(chosen),
        "intervention": intervention,
        "mix": mix,
        "available": available,
        "sequence_from": chosen[0].sequence_no if chosen else None,
        "sequence_to": chosen[-1].sequence_no if chosen else None,
        "reasons": reasons,
        "fallback_used": bool(pool) and len(chosen) < count,
        "missing_answer_key": sum(1 for q in chosen if not q.current_answer_key),
    }


def selection_stats(db: Session, user: models.User, topic_id: int) -> dict:
    scope = topic_scope(db, topic_id)
    pool = pool_for_scope(db, scope)
    attempted = _attempted_ever(db, user)
    recent = _recent_attempts(db, user, 5)
    bands: dict[str, int] = {}
    for question in pool:
        band = difficulty_band(question)
        bands[band] = bands.get(band, 0) + 1
    return {
        "topic_id": topic_id,
        "pool": len(pool),
        "seen": len([q for q in pool if q.id in attempted]),
        "unseen": len([q for q in pool if q.id not in attempted]),
        "recently_practised": len([q for q in pool if q.id in recent]),
        "bands": bands,
        "without_answer_key": len([q for q in pool if not q.current_answer_key]),
    }
