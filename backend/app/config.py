"""Central parameter registry for StudyS459 V3.

Every numeric constant used by a decision engine lives here, together with:

* ``value``       - the effective value,
* ``provenance``  - where the number comes from,
* ``confidence``  - EMPIRICAL | RESEARCH_SUPPORTED | HEURISTIC | USER_SPECIFIC | EXPERIMENTAL,
* ``note``        - what it means and what it does *not* mean.

Rules taken from the V3 master specification:

* "Exact numeric schedules must be configurable and evidence-validated."
* "Old Range + Parity logic may remain as a small question-selection signal,
  not the main intelligence."  -> it is kept as a *minor* selection signal.
* V2 numeric documents remain the source of truth for the features they own,
  but V3 priority weights are new, unvalidated defaults and are flagged as
  ``HEURISTIC`` so that they are never mistaken for evidence.

Nothing in the code base is allowed to hard-code a threshold: engines read from
``PARAMS`` (or the settings object built from it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

EMPIRICAL = "EMPIRICAL"
RESEARCH_SUPPORTED = "RESEARCH_SUPPORTED"
HEURISTIC = "HEURISTIC"
USER_SPECIFIC = "USER_SPECIFIC"
EXPERIMENTAL = "EXPERIMENTAL"

MODEL_VERSION = "v3.0.0"


@dataclass(frozen=True)
class Param:
    value: Any
    provenance: str
    confidence: str = HEURISTIC
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "note": self.note,
        }


def _p(value: Any, provenance: str, confidence: str = HEURISTIC, note: str = "") -> Param:
    return Param(value, provenance, confidence, note)


V2 = "study_system_v2_docs/14_NUMERIC_ALGORITHMS_REFERENCE.md"
V2_T = "study_system_v2_docs/05_TIME_TRACKING_AND_HABITS.md"
V2_R = "study_system_v2_docs/06_REVIEW_ALGORITHM_V2.md"
V2_W = "study_system_v2_docs/08_PLANNING_ADVICE_AFTER_30_DAYS.md"
V2_C = "study_system_v2_docs/02_CALENDAR_JALALI_IRAN.md"
V21 = "study_system_v2_1_docs"
V22 = "study_system_v2_2_docs"
V3 = "study_system_v3_docs/00_V3_MASTER_PRODUCTION_SPECIFICATION.md"
V3_1 = "study_system_v3_1_docs/05_CALENDAR_1405_1408.md"


PARAMS: Dict[str, Param] = {
    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------
    "calendar.week_start": _p("شنبه", V2_C, USER_SPECIFIC, "Iranian week starts on Saturday"),
    # V3.1 doc 06: task types are a registry; students/extensions add their own here
    "tasks.custom_types": _p([], V3_1, USER_SPECIFIC, "انواع کار مطالعهٔ سفارشی (فهرست {code,label,family,needs_questions})"),
    # V3.1 doc 07 — purposeful questioning: every answer moves a parameter a little
    "questioning.daily_max_questions": _p(4, V3_1, USER_SPECIFIC, "بیشترین سؤال آغاز/پایان روز (سقف سند: ۴)"),
    "questioning.weekly_max_questions": _p(4, V3_1, USER_SPECIFIC, "بیشترین سؤال هفتگی (سقف سند: ۴)"),
    "questioning.max_answer_delta_pct": _p(0.10, V3_1, HEURISTIC, "سقف اثر یک پاسخ واحد روی یک پارامتر"),
    "questioning.max_capacity_delta_pct": _p(0.15, V3_1, HEURISTIC, "سقف اثر تجمیعی گزارش‌های روز روی ظرفیت"),
    "questioning.max_weight_delta_pct": _p(0.15, V3_1, HEURISTIC, "سقف جابه‌جایی وزن‌های برنامه به‌خاطر پاسخ هفتگی"),
    "questioning.min_personality_evidence": _p(5, V3_1, HEURISTIC, "کمینه شواهد برای اثرگذاری ترجیح شخصیتی بر ترتیب"),
    "questioning.min_personality_confidence": _p(0.35, V3_1, HEURISTIC, "کمینه اطمینان برای اثرگذاری ترجیح شخصیتی"),
    "questioning.trait_high_threshold": _p(0.62, V3_1, HEURISTIC, "آستانه بالا بودن یک صفت برای اثرگذاری"),
    "questioning.trait_low_threshold": _p(0.38, V3_1, HEURISTIC, "آستانه پایین بودن یک صفت برای اثرگذاری"),
    "questioning.ordering_tie_epsilon": _p(0.02, V3_1, HEURISTIC, "پهنای گروه هم‌امتیاز که ترتیبش می‌تواند عوض شود"),
    "questioning.daily_question_information_threshold": _p(0.25, V3_1, HEURISTIC, "کمینه ارزش اطلاعاتی برای پرسیدن سؤال"),
    "calendar.coins_timezone": _p("Asia/Tehran", V2_C, USER_SPECIFIC),
    # V3.1 doc 05: the product must be usable for the whole ۱۴۰۵–۱۴۰۸ window
    "calendar.min_year": _p(
        1405, V3_1, USER_SPECIFIC, "پایین‌ترین سال پشتیبانی‌شده (بازهٔ V3.1: ۱۴۰۵ تا ۱۴۰۸)"
    ),
    "calendar.max_year": _p(1408, V3_1, USER_SPECIFIC, "بالاترین سال پشتیبانی‌شده (بازهٔ V3.1: ۱۴۰۵ تا ۱۴۰۸)"),
    "calendar.season.school_term_months": _p([7, 8, 9, 10, 11, 12, 1, 2, 3], V2_C, HEURISTIC),
    # ------------------------------------------------------------------
    # Rewards / coins (V2 owns these exact numbers)
    # ------------------------------------------------------------------
    "reward.wake_target_hour": _p(7, V2, USER_SPECIFIC),
    "reward.wake_target_minute": _p(0, V2, USER_SPECIFIC),
    "reward.wake_early_bonus_time": _p("06:45", V2, USER_SPECIFIC),
    "reward.wake_late_limit": _p("07:15", V2, USER_SPECIFIC, "after this no wake-up coins"),
    "reward.coins_wake_up": _p(15, V2, USER_SPECIFIC),
    "reward.coins_wake_up_early_bonus": _p(5, V2, USER_SPECIFIC),
    "reward.coins_all_daily_tests": _p(40, V2, USER_SPECIFIC),
    "reward.coins_task_completed": _p(8, V2, USER_SPECIFIC),
    "reward.coins_correct_answer": _p(2, V2, USER_SPECIFIC),
    "reward.coins_successful_review": _p(3, V2, USER_SPECIFIC),
    "reward.coins_daily_goal": _p(20, V2, USER_SPECIFIC),
    "reward.coins_weekly_goal": _p(70, V2, USER_SPECIFIC),
    "reward.coins_streak_day": _p(10, V2, USER_SPECIFIC),
    "reward.imported_sessions_earn_coins": _p(False, V2, USER_SPECIFIC),
    # ------------------------------------------------------------------
    # Review engine
    # ------------------------------------------------------------------
    "review.max_questions_per_session": _p(25, V2_R, USER_SPECIFIC),
    "review.min_cluster_size": _p(8, V2_R, USER_SPECIFIC),
    "review.critical_wrong_count": _p(2, V2_R, HEURISTIC),
    "review.critical_max_days": _p(2, V2_R, HEURISTIC),
    "review.normal_max_days": _p(3, V2_R, HEURISTIC),
    "review.cluster_common_parent_depth": _p(2, V2_R, HEURISTIC),
    # ------------------------------------------------------------------
    # Question selection / parity (kept as a *minor* signal in V3)
    # ------------------------------------------------------------------
    "selection.default_first_parity": _p("odd", V2, USER_SPECIFIC),
    "selection.parity_weight": _p(10, V2, HEURISTIC, "V2 weight; V3 keeps it as minor signal only"),
    "selection.max_parity_share": _p(0.25, V3, HEURISTIC, "parity may never dominate selection"),
    # ------------------------------------------------------------------
    # Capacity
    # ------------------------------------------------------------------
    "capacity.default_sleep_time": _p("23:30", V2, USER_SPECIFIC),
    "capacity.default_personal_fixed_minutes": _p(45, V2, USER_SPECIFIC),
    "capacity.default_school_end_time": _p("13:30", V2, USER_SPECIFIC),
    "capacity.no_school_multiplier": _p(1.35, V2, USER_SPECIFIC),
    "capacity.no_school_min_minutes": _p(180, V2, USER_SPECIFIC),
    "capacity.min_days_before_habitual_estimate": _p(30, V2_T, HEURISTIC,
                                                     "before 30 active days stay conservative"),
    "capacity.history_window_days": _p(21, V3, HEURISTIC),
    "capacity.max_daily_minutes": _p(300, V3, HEURISTIC, "anti over-planning ceiling for one day"),
    "capacity.overload_tolerance": _p(1.0, V3, HEURISTIC, "planned minutes / realistic capacity"),
    "capacity.gradual_change_step": _p(0.15, V21, HEURISTIC, "capacity adapts gradually"),
    # ------------------------------------------------------------------
    # Session / time-on-task
    # ------------------------------------------------------------------
    "session.bundle_min_minutes": _p(60, V2_T, USER_SPECIFIC),
    "session.bundle_max_minutes": _p(120, V2_T, USER_SPECIFIC),
    "session.first_month_fallback_low": _p(60, V3, HEURISTIC),
    "session.first_month_fallback_high": _p(120, V3, HEURISTIC),
    "session.min_minutes_per_question": _p(1.5, V3, HEURISTIC),
    "session.max_minutes_per_question": _p(6.0, V3, HEURISTIC),
    "duration.min_observations_for_personal_range": _p(8, V3, HEURISTIC),
    "duration.min_observations_for_topic_model": _p(4, V3, HEURISTIC),
    "duration.wide_range_low_factor": _p(0.75, V3, HEURISTIC),
    "duration.wide_range_high_factor": _p(1.35, V3, HEURISTIC),
    "duration.tight_range_low_factor": _p(0.92, V3, HEURISTIC),
    "duration.tight_range_high_factor": _p(1.12, V3, HEURISTIC),
    "duration.drift_threshold": _p(0.20, V3, HEURISTIC, "systematic change detection"),
    "duration.drift_window": _p(5, V3, HEURISTIC),
    # ------------------------------------------------------------------
    # Timed mode adaptation
    # ------------------------------------------------------------------
    "timed.min_attempts_for_adaptation": _p(20, V2_T, HEURISTIC),
    "timed.accuracy_threshold": _p(0.75, V2_T, HEURISTIC),
    "timed.step_factor": _p(0.80, V2_T, HEURISTIC),
    "timed.min_seconds": _p(60, V2_T, HEURISTIC),
    # ------------------------------------------------------------------
    # Priority engine (V3 formula) - weights are HEURISTIC and configurable
    # ------------------------------------------------------------------
    "priority.weight.exam_need": _p(0.22, V3, HEURISTIC),
    "priority.weight.goal_need": _p(0.14, V3, HEURISTIC),
    "priority.weight.learning_need": _p(0.16, V3, HEURISTIC),
    "priority.weight.coverage_need": _p(0.12, V3, HEURISTIC),
    "priority.weight.review_need": _p(0.10, V3, HEURISTIC),
    "priority.weight.prerequisite_need": _p(0.06, V3, HEURISTIC),
    "priority.weight.retention_risk": _p(0.07, V3, HEURISTIC),
    "priority.weight.behavioral_fit": _p(0.05, V3, HEURISTIC),
    "priority.weight.opportunity": _p(0.04, V3, HEURISTIC),
    "priority.weight.capacity_cost": _p(0.08, V3, HEURISTIC),
    "priority.weight.recent_saturation": _p(0.06, V3, HEURISTIC),
    "priority.saturation_window_days": _p(7, V3, HEURISTIC),
    "priority.saturation_reference_attempts": _p(2.0, V3, HEURISTIC),
    "priority.untested_question_weight": _p(0.25, V3, HEURISTIC),
    "priority.low_coverage_threshold": _p(0.35, V3, HEURISTIC),
    "priority.high_accuracy_threshold": _p(0.75, V3, HEURISTIC),
    "priority.weak_accuracy_threshold": _p(0.55, V3, HEURISTIC),
    "priority.repeated_error_reference": _p(2, V3, HEURISTIC),
    # ------------------------------------------------------------------
    # Learning state / retention
    # ------------------------------------------------------------------
    "learning.confidence_min_attempts": _p(12, V3, HEURISTIC, "evidence needed for confident estimate"),
    "learning.confidence_reference_attempts": _p(40, V3, HEURISTIC),
    "learning.difficulty_reference": _p(2.0, V3, HEURISTIC),
    "learning.recency_half_life_days": _p(14.0, V3, RESEARCH_SUPPORTED,
                                          "broad default; spacing parameters need validation"),
    "retention.target_success": _p(0.85, V3, HEURISTIC),
    "retention.stability_base_days": _p(2.0, V3, RESEARCH_SUPPORTED),
    "retention.stability_growth": _p(9.0, V3, RESEARCH_SUPPORTED,
                                     "fixed-interval/forgetting-curve placeholder - must be validated"),
    "retention.min_days": _p(1.0, V3, HEURISTIC),
    "retention.max_days": _p(60.0, V3, HEURISTIC),
    "retention.risk_horizon_days": _p(10.0, V3, HEURISTIC),
    # ------------------------------------------------------------------
    # Recommendation / intervention choice
    # ------------------------------------------------------------------
    "recommendation.diagnostic_uncertainty_threshold": _p(0.45, V3, HEURISTIC,
                                                          "prefer a short diagnostic over remediation"),
    "recommendation.diagnostic_min_question_count": _p(6, V3, HEURISTIC),
    "recommendation.diagnostic_max_question_count": _p(12, V3, HEURISTIC),
    "recommendation.min_question_count": _p(8, V3, HEURISTIC),
    "recommendation.max_question_count": _p(25, V3, HEURISTIC),
    "recommendation.easy_question_ratio": _p(0.60, V3, HEURISTIC),
    "recommendation.hard_question_ratio": _p(0.35, V3, HEURISTIC),
    "recommendation.max_suggestions_per_day": _p(3, V3, HEURISTIC),
    "recommendation.quiet_max_per_day": _p(1, V22, USER_SPECIFIC),
    "recommendation.quiet_dismiss_hours": _p(24, V22, USER_SPECIFIC),
    "recommendation.package_min_questions": _p(10, V22, USER_SPECIFIC),
    "recommendation.package_max_questions": _p(20, V22, USER_SPECIFIC),
    "recommendation.accept_feedback_weight": _p(0.25, V3, HEURISTIC,
                                                "accepted != proof of quality"),
    # ------------------------------------------------------------------
    # Exam / goals
    # ------------------------------------------------------------------
    "exam.urgency_horizon_days": _p(21, V3, HEURISTIC),
    "exam.urgency_boost": _p(0.45, V3, HEURISTIC),
    "exam.overlap_weight": _p(0.5, V3, HEURISTIC),
    "exam.calendar_horizon_days": _p(90, V3, HEURISTIC, "default exam calendar window (~3 months)"),
    "exam.mock_prep_share": _p(0.35, V3, HEURISTIC, "share of week for nearest exam"),
    "goal.horizon_days": _p(90, V3, USER_SPECIFIC, "three month goal"),
    "goal.milestone_min_days": _p(7, V3, HEURISTIC),
    "goal.progress_on_track_tolerance": _p(0.10, V3, HEURISTIC),
    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------
    "planning.max_tasks_per_day": _p(6, V3, HEURISTIC),
    "planning.max_tasks_per_week": _p(30, V3, HEURISTIC),
    "planning.midweek_check_weekday": _p("چهارشنبه", V2, USER_SPECIFIC),
    "planning.midweek_progress_threshold": _p(0.50, V2, USER_SPECIFIC),
    "planning.catchup_multiplier": _p(1.5, V2, USER_SPECIFIC),
    "planning.protected_task_minutes": _p(45, V3, HEURISTIC,
                                          "critical work protected during recovery"),
    "planning.recovery_horizon_days": _p(5, V3, HEURISTIC),
    "planning.recovery_max_shift_days": _p(3, V3, HEURISTIC,
                                           "missed work is spread, never dumped on tomorrow"),
    "planning.question_information_threshold": _p(0.30, V3, HEURISTIC,
                                                  "ask only when it can change a decision"),
    "planning.max_adaptive_questions": _p(5, V3, HEURISTIC),
    # ------------------------------------------------------------------
    # Behaviour / state / profile
    # ------------------------------------------------------------------
    "behavior.state_dimensions": _p(
        ["energy", "focus", "motivation", "stress", "fatigue", "readiness"], V21, HEURISTIC),
    "behavior.personality_dimensions": _p(
        ["discipline", "planning_preference", "procrastination", "competition",
         "reward_sensitivity", "stress_tolerance", "routine_preference",
         "novelty_preference", "self_criticism", "goal_orientation"], V21, HEURISTIC),
    "behavior.personality_max_delta_per_answer": _p(0.08, V22, USER_SPECIFIC,
                                                    "one answer must never jump a dimension"),
    "behavior.personality_confident_threshold": _p(0.40, V22, USER_SPECIFIC,
                                                   "below this the dimension stays out of planning"),
    "behavior.min_days_for_capacity_advice": _p(30, V2_T, USER_SPECIFIC),
    "behavior.pattern_min_evidence": _p(6, V3, HEURISTIC),
    "behavior.long_task_split_minutes": _p(75, V21, HEURISTIC),
    "behavior.warmup_question_count": _p(10, V22, USER_SPECIFIC,
                                         "example experiment: 10 easy questions before hard work"),
    # ------------------------------------------------------------------
    # Confidence / evidence policy
    # ------------------------------------------------------------------
    "confidence.low": _p(0.34, V21, HEURISTIC),
    "confidence.medium": _p(0.67, V21, HEURISTIC),
    "confidence.max_by_evidence": _p([[1, 0.35], [3, 0.5], [10, 0.7], [25, 0.85], [60, 0.95]], V21, HEURISTIC),
    # ------------------------------------------------------------------
    # Experiments / research
    # ------------------------------------------------------------------
    "experiment.min_observations_per_arm": _p(5, V3, HEURISTIC),
    "experiment.min_effect_for_signal": _p(0.15, V3, HEURISTIC),
    "evidence.levels": _p(["EMPIRICAL", "RESEARCH_SUPPORTED", "HEURISTIC", "USER_SPECIFIC", "EXPERIMENTAL"],
                          V3, HEURISTIC),
    # ------------------------------------------------------------------
    # Onboarding / adaptive questionnaire
    # ------------------------------------------------------------------
    "onboarding.max_questions_per_session": _p(12, V21, USER_SPECIFIC),
    "onboarding.min_questions": _p(8, V21, USER_SPECIFIC),
    "onboarding.target_questions": _p(30, V21, USER_SPECIFIC),
    "onboarding.uncertainty_stop_threshold": _p(0.30, V3, HEURISTIC),
}


def value(key: str) -> Any:
    return PARAMS[key].value


def param(key: str) -> Param:
    return PARAMS[key]


def snapshot() -> Dict[str, Dict[str, Any]]:
    """Full parameter registry with provenance - exposed by GET /config/params."""
    return {key: p.as_dict() for key, p in sorted(PARAMS.items())}


def export_override(overrides: Dict[str, Any]) -> Dict[str, Param]:
    """Build an experiment/override aware parameter set without mutating defaults."""
    merged = dict(PARAMS)
    for key, raw in overrides.items():
        base = merged.get(key)
        if base is None:
            merged[key] = _p(raw, "user_override", USER_SPECIFIC)
        else:
            merged[key] = Param(raw, "user_override", USER_SPECIFIC, f"overrides {base.provenance}")
    return merged


@dataclass
class AppSettings:
    """Non-numeric runtime settings."""

    app_name: str = "StudyS459 V3"
    database_url: str = "sqlite:///./data/studys459.db"
    frontend_dir: str = "frontend"
    default_timezone: str = "Asia/Tehran"
    seed_books: bool = True
    telemetry: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)
