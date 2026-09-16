"""مسیرهای لایهٔ Behavioral Intelligence — V2.1.

Profile / Questionnaire / Behavior / State + Rewards.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_user
from app.db import get_db
from app.domain import behavior as behavior_mod
from app.domain import questionnaire as q_mod
from app.domain import rewards as rewards_mod
from app.domain import state as state_mod
from app.domain.personality import profile_summary
from app.models import User

router = APIRouter()


# ------------------------------- Rewards (V2) --------------------------------

@router.post("/rewards/wake-up")
def wake_up(db: Session = Depends(get_db), user: User = Depends(get_user)):
    out = rewards_mod.wake_up(db, user)
    behavior_mod.log_event(db, user.id, "wake_up_recorded", {"coins": out.get("coins", 0)})
    db.commit()
    return out


@router.get("/rewards/summary")
def rewards(db: Session = Depends(get_db), user: User = Depends(get_user)):
    db.commit()
    return rewards_mod.rewards_summary(db, user)


@router.get("/rewards/events")
def reward_events(db: Session = Depends(get_db), user: User = Depends(get_user)):
    s = rewards_mod.rewards_summary(db, user)
    return s["events"]


@router.get("/rewards/badges")
def badges(db: Session = Depends(get_db), user: User = Depends(get_user)):
    db.commit()
    return rewards_mod.rewards_summary(db, user)["badges"]


# ------------------------------- User model (V2.1) ---------------------------

@router.get("/user-model")
def user_model(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return profile_summary(db, user)


class PrefsBody(BaseModel):
    preferred_study_time: str | None = None
    plan_style: str | None = None
    task_size: str | None = None


@router.patch("/user-model/preferences")
def patch_prefs(body: PrefsBody, db: Session = Depends(get_db),
                user: User = Depends(get_user)):
    from app.domain.personality import get_profile
    p = get_profile(db, user)
    prefs = dict(p.preferences_json or {})
    for k, v in body.model_dump(exclude_none=True).items():
        if v is not None:
            prefs[k] = {"value": v, "confidence": 0.9, "evidence_count": 1,
                        "source": "self_report"}
    p.preferences_json = prefs
    db.commit()
    return {"ok": True, "preferences": prefs}


# ------------------------------- Onboarding (V2.1) ---------------------------

class AnswerBody(BaseModel):
    question_key: str
    answer: object


@router.post("/onboarding/questions/next")
def next_question(db: Session = Depends(get_db), user: User = Depends(get_user)):
    q = q_mod.next_question(db, user)
    if q is None:
        return {"complete": True, "summary": q_mod.summary(db, user)}
    return {"complete": False, "question": q, "summary": q_mod.summary(db, user)}


@router.post("/onboarding/answers")
def submit_answer(body: AnswerBody, db: Session = Depends(get_db),
                  user: User = Depends(get_user)):
    out = q_mod.apply_answer(db, user, body.question_key, body.answer)
    db.commit()
    if not out.get("ok"):
        raise HTTPException(400, out.get("reason"))
    behavior_mod.log_event(db, user.id, "questionnaire_answered", {
        "question_key": body.question_key}, source="self_report")
    return {"ok": True, "summary": q_mod.summary(db, user)}


@router.get("/onboarding/summary")
def onboarding_summary(db: Session = Depends(get_db), user: User = Depends(get_user)):
    s = q_mod.summary(db, user)
    s["onboarding_done"] = (user.settings_json or {}).get("onboarding_done", False)
    return s


@router.post("/onboarding/finish")
def finish_onboarding(db: Session = Depends(get_db), user: User = Depends(get_user)):
    s = user.settings_json or {}
    s["onboarding_done"] = True
    user.settings_json = s
    db.commit()
    return {"ok": True}


# ------------------------------- Behavior (V2.1) -----------------------------

@router.get("/behavior/summary")
def behavior_summary(db: Session = Depends(get_db), user: User = Depends(get_user)):
    db.commit()
    return behavior_mod.behavior_summary(db, user)


@router.get("/behavior/features")
def behavior_features(db: Session = Depends(get_db), user: User = Depends(get_user)):
    db.commit()
    return behavior_mod.compute_features(db, user.id)


# ------------------------------- State (V2.1) --------------------------------

@router.get("/state/current")
def current_state(db: Session = Depends(get_db), user: User = Depends(get_user)):
    return state_mod.current_state(db, user)


class CheckInBody(BaseModel):
    energy: int  # 1..5
    focus: int
    motivation: int
    stress: int
    fatigue: int
    sleep_hours: float = 7


@router.post("/state/check-in")
def check_in(body: CheckInBody, db: Session = Depends(get_db), user: User = Depends(get_user)):
    for k in ("energy", "focus", "motivation", "stress", "fatigue"):
        v = getattr(body, k)
        if not (1 <= v <= 5):
            raise HTTPException(400, f"{k} باید بین ۱ تا ۵ باشد.")
    snap = state_mod.check_in(db, user, body.model_dump())
    db.commit()
    return {
        "ok": True,
        "readiness": round(snap.readiness, 3),
        "message": "وضعیت امروزت ثبت شد و در پیشنهادهای امروز لحاظ می‌شود.",
    }
