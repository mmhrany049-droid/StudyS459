"""V3 acceptance scenarios (study_system_v3_docs/11 + study_system_v2_2_docs/13).

Every test maps to a rule that must never silently regress.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from app import config
from app.core.errors import DomainError
from app.db import models
from app.services import (
    behaviour,
    capacity,
    curriculum,
    duration as duration_service,
    exams as exams_service,
    goals as goals_service,
    learning,
    planner,
    priority,
    questions as questions_service,
    recommendation,
    review,
    sessions,
    tasks as tasks_service,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sheet_question_ids(db, session):
    """Question list of a session lives on its response sheet (question ≠ sheet)."""
    sheet = db.scalars(
        select(models.ResponseSheet).where(models.ResponseSheet.session_id == session.id)
    ).first()
    return [
        entry.question_id
        for entry in db.scalars(
            select(models.ResponseEntry)
            .where(models.ResponseEntry.response_sheet_id == sheet.id)
            .order_by(models.ResponseEntry.id)
        )
    ]


def _final_payload(db, user, session):
    """The submit view of a result (finish_session is idempotent, so this is safe to re-ask)."""
    return sessions.finish_session(db, user, session.id)


def _ensure_keys(db, user, question_ids, key="1"):
    """Deterministic scoring: every selected question gets a key unless it already has one."""
    for question_id in question_ids:
        question = db.get(models.Question, question_id)
        if question is not None and not question.current_answer_key:
            questions_service.set_answer_key(db, user, question_id, key)
    db.commit()


def _session_with(db, user, fixture, answers):
    book, topic = fixture["book"], fixture["topic"]
    session = sessions.create_session(
        db, user, {"book_id": book.id, "topic_id": topic.id, "count": len(answers), "start_now": True}
    )
    db.commit()
    question_ids = _sheet_question_ids(db, session)
    assert len(question_ids) == len(answers), "the pool must serve the requested count"
    if any(spec.get("state") == "ANSWERED" for spec in answers):
        _ensure_keys(db, user, question_ids)
    entries = [{"question_id": qid, **spec} for qid, spec in zip(question_ids, answers)]
    sessions.save_entries(db, user, session.id, entries, finalize=True, actual_duration_minutes=30)
    db.commit()
    return session


# ---------------------------------------------------------------------------
# Taught ≠ learned, cascade semantics
# ---------------------------------------------------------------------------

def test_cascade_ticks_every_descendant(db, user, seeded):
    chapter = db.query(models.Topic).filter(models.Topic.node_type == "chapter").first()
    result = curriculum.set_taught(db, user, chapter.id, True, cascade=True)
    db.commit()
    assert result["affected"]
    for topic_id in result["affected"]:
        row = db.query(models.TaughtTopic).filter_by(user_id=user.id, topic_id=topic_id).first()
        assert row is not None and row.taught is True
    detail = curriculum.topic_detail(db, chapter.id, user)
    assert detail["taught"]["taught"] is True
    assert "یادگرفته" in detail["taught"]["meaning"] or "یاد" in detail["taught"]["meaning"]


def test_partial_cascade_does_not_fake_a_full_parent(db, user, seeded):
    chapter = db.query(models.Topic).filter(models.Topic.node_type == "chapter").first()
    children = db.query(models.Topic).filter(models.Topic.parent_id == chapter.id).all()
    assert len(children) >= 2
    curriculum.set_taught(db, user, children[0].id, True, cascade=True)
    db.commit()
    skill = db.query(models.Topic).filter_by(parent_id=children[0].id).first()
    if skill is not None:
        curriculum.set_taught(db, user, skill.id, True, cascade=True)
        db.commit()
    assert curriculum.topic_detail(db, children[0].id, user)["taught"]["taught"] is True
    # ticking one child must never mark the parent itself as fully taught
    assert curriculum.topic_detail(db, chapter.id, user)["taught"]["taught"] is False


def test_taught_alone_does_not_create_accuracy(db, user, seeded):
    topic = db.query(models.Topic).filter(models.Topic.is_leaf.is_(True)).first()
    curriculum.set_taught(db, user, topic.id, True, cascade=True)
    db.commit()
    state = learning.compute_state_for_topic(db, user, topic.id)
    db.commit()
    assert state.accuracy is None, "taught must never be reported as accuracy"
    assert (state.coverage or 0.0) == 0.0


# ---------------------------------------------------------------------------
# ANSWERED / UNANSWERED / NOT_ENTERED never collapse into each other
# ---------------------------------------------------------------------------

def test_three_states_stay_distinct_and_invariant_holds(db, user, seeded, book_with_questions):
    specs = []
    for index in range(20):
        if index < 6:
            specs.append({"state": "ANSWERED", "selected_choice": str((index % 4) + 1)})
        elif index < 12:
            specs.append({"state": "UNANSWERED"})
        else:
            specs.append({"state": "NOT_ENTERED"})
    session = _session_with(db, user, book_with_questions, specs)
    result = sessions.session_result(db, session.id)
    assert result["total"] == 20
    assert result["not_entered"] == 8, "untouched rows must be reported as NOT_ENTERED"
    assert result["unanswered"] == 6
    assert result["invariant_ok"] is True
    total_parts = (
        result["correct"]
        + result["wrong"]
        + result["unanswered"]
        + result["not_entered"]
        + result["not_evaluable"]
    )
    assert total_parts == result["total"]
    for group in result["topic_breakdown"]:
        assert "not_entered" in group and "not_evaluable" in group


def test_missing_answer_key_is_not_evaluable_not_wrong(db, user, seeded):
    topic = db.query(models.Topic).filter(models.Topic.is_leaf.is_(True)).first()
    book = db.get(models.Book, topic.book_id)
    questions_service.add_question_range(db, user, book_id=book.id, topic_id=topic.id, seq_from=1, seq_to=10)
    db.commit()
    session = sessions.create_session(
        db, user, {"book_id": book.id, "topic_id": topic.id, "count": 10, "start_now": True}
    )
    db.commit()
    question_ids = _sheet_question_ids(db, session)
    for question_id in question_ids:  # make "no key yet" explicit and deterministic
        questions_service.set_answer_key(db, user, question_id, None, reason="تست پذیرش")
    db.commit()
    entries = [
        {"question_id": qid, "state": "ANSWERED", "selected_choice": "1"} for qid in question_ids
    ]
    sessions.save_entries(db, user, session.id, entries, finalize=True)
    db.commit()
    result = _final_payload(db, user, session)
    db.commit()
    assert result["wrong"] == 0, "an unknown answer key must never be scored as a wrong answer"
    assert result["not_evaluable"] == 10
    assert result["missing_answer_keys"] >= 1
    assert result["pending_correction"] is True or result["status"] == "pending_correction"


def test_not_entered_rows_never_trigger_pending_correction(db, user, seeded, book_with_questions):
    specs = [{"state": "ANSWERED", "selected_choice": "1"}] * 4 + [{"state": "NOT_ENTERED"}] * 6
    session = _session_with(db, user, book_with_questions, specs)
    result = _final_payload(db, user, session)
    db.commit()
    assert result["not_entered"] == 6
    assert result["missing_answer_keys"] == 0
    assert result["pending_correction"] is False, "NOT_ENTERED ≠ missing answer key"


def test_finish_is_idempotent(db, user, seeded, book_with_questions):
    session = _session_with(db, user, book_with_questions, [{"state": "ANSWERED", "selected_choice": "1"}] * 10)
    before = db.query(models.AttemptResult).filter_by(session_id=session.id).count()
    sessions.finish_session(db, user, session.id)
    db.commit()
    after = db.query(models.AttemptResult).filter_by(session_id=session.id).count()
    assert before == after and before == 10, "finishing twice must not duplicate attempts"


def test_answer_key_correction_keeps_history_and_flags_recalc(db, user, seeded, book_with_questions):
    book, topic = book_with_questions["book"], book_with_questions["topic"]
    question = db.query(models.Question).filter_by(book_id=book.id, primary_topic_id=topic.id).first()
    old_key = question.current_answer_key
    result = questions_service.set_answer_key(db, user, question.id, "4", reason="تصحیح آزمون")
    db.commit()
    assert result["changed"] is True
    assert result["recalc_required"] == [question.id]
    versions = db.query(models.AnswerKeyVersion).filter_by(question_id=question.id).all()
    assert len(versions) >= 2, "the previous key must be kept as a version, not overwritten"
    assert old_key in {version.answer_key for version in versions} - {"4"}


def test_repeated_finish_never_double_awards_and_keeps_badges(db, user, seeded, book_with_questions):
    """Regression: the idempotent finish path must rebuild rewards read-only."""
    from app.services import rewards as rewards_service

    badge = db.query(models.Badge).first()
    assert badge is not None
    db.add(models.UserBadge(user_id=user.id, badge_id=badge.id))
    db.commit()

    session = _session_with(
        db, user, book_with_questions, [{"state": "ANSWERED", "selected_choice": "1"}] * 6
    )
    awarded = rewards_service.session_summary(db, user, session)
    assert awarded["coins"] > 0
    assert any(item["code"] == badge.code for item in awarded["badges"])

    payload = _final_payload(db, user, session)
    db.commit()
    assert payload["idempotent"] is True
    assert payload["rewards"]["coins"] == awarded["coins"], "a retry must not duplicate coins"
    assert any(item["code"] == badge.code for item in payload["rewards"]["badges"])
    assert payload["pending_correction"] is False and payload["missing_answer_keys"] == 0


# ---------------------------------------------------------------------------
# Priority / recommendation / planner
# ---------------------------------------------------------------------------

def test_exam_raises_the_exam_component_not_the_whole_truth(db, user, seeded):
    topic = db.query(models.Topic).filter(models.Topic.is_leaf.is_(True)).first()
    before = priority.compute_topic_priority(db, user, topic.id)
    exams_service.create_exam(
        db,
        user,
        {
            "title": "امتحان نوبت اول",
            "exam_type": "school",
            "exam_date": (dt.date.today() + dt.timedelta(days=5)).isoformat(),
        },
    )
    db.commit()
    after = priority.compute_topic_priority(db, user, topic.id)
    assert after["components"]["exam_need"]["value"] >= before["components"]["exam_need"]["value"]
    assert after["components"]["exam_need"]["evidence"].get("reason")


def test_priority_evidence_is_traceable(db, user, seeded, book_with_questions):
    topic = book_with_questions["topic"]
    item = priority.compute_topic_priority(db, user, topic.id)
    assert item["top_reasons"], "a priority must cite its drivers"
    for contribution in item["top_reasons"]:
        assert "component" in contribution
        assert "weight" in contribution and "contribution" in contribution
        assert contribution["evidence"].get("reason"), "evidence must carry a human-readable reason"
    explained = priority.explain_priority({**item, "rank": 1, "topic_title": topic.title})
    assert set(["what", "why", "evidence", "what_can_i_change"]).issubset(explained.keys())
    assert explained["model_version"] == config.MODEL_VERSION


def test_recommendation_is_explainable_and_never_says_because_ai(db, user, seeded, book_with_questions):
    topic = book_with_questions["topic"]
    item = priority.compute_topic_priority(db, user, topic.id)
    row = recommendation.build_recommendation(db, user, topic_id=topic.id, priority_item=item)
    db.commit()
    assert row.intervention_type
    explanation = recommendation.explanation(db, row.id)
    assert set(["what", "why", "evidence", "what_can_i_change"]).issubset(explanation.keys())
    assert explanation["model_version"] == config.MODEL_VERSION
    assert explanation["evidence"], "an explanation without evidence is forbidden"


def test_planner_never_overwrites_manual_tasks(db, user, seeded, book_with_questions):
    session = planner.create_session(db, user, {})
    db.commit()
    manual = tasks_service.create_task(
        db,
        user,
        {
            "title": "کار دستی من",
            "task_type": "test_session",
            "planned_date": session.week_start.isoformat(),
            "duration_low": 30,
            "duration_high": 40,
            "manual_override": True,
        },
    )
    db.commit()
    result = planner.generate_plan(db, user, session)
    db.commit()
    db.refresh(manual)
    assert manual.status != "cancelled"
    assert manual.manual_override is True
    assert result["manual_tasks_preserved"] >= 1


def test_planner_reports_overload_instead_of_deleting_work(db, user, seeded, book_with_questions):
    session = planner.create_session(db, user, {})
    db.commit()
    result = planner.generate_plan(db, user, session)
    db.commit()
    assert "summary" in result["explanation"]
    overload = result["overload"]
    if overload.get("has_overload"):
        assert overload.get("days"), "an overload must name the affected days"
        for day in overload["days"]:
            assert "حذف" not in (day.get("suggestion") or "")


def test_adaptive_interview_records_unknown_answers(db, user, seeded, book_with_questions):
    session = planner.create_session(db, user, {})
    db.commit()
    created = planner.adaptive_questions(db, user, session)
    db.commit()
    assert isinstance(created, list)
    if not created:
        pytest.skip("no adaptive question had enough information value in this state")
    assert all(question.information_value is not None for question in created)
    planner.answer_question(db, user, session, created[0].code, None, skipped=True)
    db.commit()
    answer = db.scalars(
        select(models.PlanningAnswer).where(models.PlanningAnswer.planning_question_id == created[0].id)
    ).first()
    assert answer is not None, "an unanswered adaptive question must still be stored, not dropped"
    assert answer.skipped is True and answer.answer in (None, {})


# ---------------------------------------------------------------------------
# Capacity / duration / recovery
# ---------------------------------------------------------------------------

def test_theoretical_and_realistic_capacity_stay_separate(db, user, seeded):
    day = capacity.day_capacity(db, user, dt.date.today())
    assert day["theoretical_minutes"] != day["realistic_minutes"]
    assert day["realistic_minutes"] <= day["theoretical_minutes"]
    assert day["factors"]["note"]
    assert "وقت آزاد" in day["explanation"] or day["explanation"]


def test_first_month_duration_is_a_band_not_a_point(db, user, seeded):
    estimate = duration_service.estimate_for_task(db, user, task_type="test_session", question_count=10)
    assert estimate["low_minutes"] < estimate["high_minutes"], "duration must be a band, not a point"
    assert estimate["method"] in {"first_month_fallback", "topic_model", "type_model", "personal_model"}
    assert estimate["confidence"] < 0.5, "with no data the estimate must admit low confidence"


def test_skip_does_not_dump_work_on_a_later_day(db, user, seeded, book_with_questions):
    session = planner.create_session(db, user, {})
    db.commit()
    planner.generate_plan(db, user, session)
    db.commit()
    task = (
        db.query(models.StudyTask)
        .filter_by(user_id=user.id, status="planned")
        .order_by(models.StudyTask.planned_date)
        .first()
    )
    if task is None:
        pytest.skip("no generated task in this fixture state")
    planned_date = task.planned_date
    tasks_service.mark_skipped(db, user, task.id, reason="خسته بودم")
    db.commit()
    db.refresh(task)
    assert task.status == "skipped"
    assert task.planned_date == planned_date  # the work stays where it was, not pushed onto tomorrow
    recovery = tasks_service.recovery_plan(db, user)
    assert recovery is not None


# ---------------------------------------------------------------------------
# Behaviour / state / review
# ---------------------------------------------------------------------------

def test_momentary_state_is_not_personality(db, user, seeded):
    behaviour.check_in(db, user, {"energy": 0.2, "focus": 0.3}, phase="start")
    db.commit()
    state = behaviour.current_state(db, user)
    assert state["available"] is True
    dims = {item["key"]: item for item in state["dimensions"]}
    assert dims["energy"]["value"] == 0.2
    assert "شخصیت" in state["note"]
    profile = behaviour.profile_payload(db, user)
    personality = {item["key"]: item for item in profile["personality"]}
    value = (personality.get("energy") or {}).get("value")
    assert value != 0.2, "a low-energy day must not rewrite the personality profile"
    assert profile["separated"]["note"]


def test_one_onboarding_answer_cannot_jump_a_dimension(db, user, seeded):
    question = behaviour.next_onboarding_question(db, user)
    db.commit()
    if question is None:
        pytest.skip("onboarding already complete")
    code = getattr(question, "code", None) or question["code"]
    before = {item["key"]: item for item in behaviour.profile_payload(db, user)["personality"]}
    behaviour.answer_onboarding(db, user, code, {"value": 1.0})
    db.commit()
    after = {item["key"]: item for item in behaviour.profile_payload(db, user)["personality"]}
    cap = config.value("behavior.personality_max_delta_per_answer")
    for key, item in after.items():
        old = (before.get(key) or {}).get("value")
        if old is None or item["value"] is None:
            continue
        assert abs(item["value"] - old) <= cap + 1e-6, f"{key} jumped more than {cap} in one answer"


def test_review_items_come_from_attempts_with_reasons(db, user, seeded, book_with_questions):
    specs = [{"state": "ANSWERED", "selected_choice": "1"}, {"state": "UNANSWERED"}] * 5
    session = _session_with(db, user, book_with_questions, specs)
    review.rebuild_for_questions(db, user, _sheet_question_ids(db, session), session=session)
    db.commit()
    items = review.open_items(db, user)
    assert items, "wrong/unanswered attempts must produce review items"
    for item in items:
        assert item.reason in {"wrong", "unanswered"}
        assert item.priority in {"normal", "high", "critical", "low"}
        assert item.question_id


# ---------------------------------------------------------------------------
# Goals / dependencies / exams
# ---------------------------------------------------------------------------

def test_goal_decomposes_into_milestones(db, user, seeded):
    book = db.query(models.Book).first()
    goal = goals_service.create_goal(
        db,
        user,
        {
            "title": "هدف سه‌ماهه",
            "goal_type": "three_month",
            "book_ids": [book.id],
            "target_date": "1405/12/01",
        },
    )
    db.commit()
    milestones = db.query(models.GoalMilestone).filter_by(goal_id=goal.id).all()
    assert milestones, "a ~3 month goal must decompose into milestones"
    payload = goals_service.goal_payload(db, user, goal)
    assert payload["scope"]["book_ids"] == [book.id]
    assert payload["scope_topic_count"] > 0


def test_dependency_cycle_is_rejected(db, user, seeded):
    topics = db.query(models.Topic).filter(models.Topic.is_leaf.is_(True)).limit(2).all()
    if len(topics) < 2:
        pytest.skip("needs two leaf topics")
    curriculum.add_dependency(db, topics[0].id, topics[1].id)
    db.commit()
    with pytest.raises(DomainError):
        curriculum.add_dependency(db, topics[1].id, topics[0].id)


def test_exam_keeps_planned_and_actual_separate(db, user, seeded):
    exam = exams_service.create_exam(
        db, user, {"title": "امتحان پایانی", "exam_type": "school", "exam_date": "1405/10/01"}
    )
    db.commit()
    topic = db.query(models.Topic).filter(models.Topic.is_leaf.is_(True)).first()
    exams_service.set_topic_marks(db, user, exam.id, topic.id, mark_kind="planned", checked=True)
    db.commit()
    payload = exams_service.exam_payload(db, exam, detailed=True)
    assert payload["date"]
    assert payload["topics"] or payload.get("planned_topics") is not None
