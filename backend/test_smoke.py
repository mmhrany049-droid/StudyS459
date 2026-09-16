"""تست دود — پوشش قوانین کلیدی V1/V2/V2.1 (Acceptance Tests)."""
import datetime as dt
import json
import os
import sys

os.environ["SS459_DB"] = "/tmp/ss459_smoke.db"
if os.path.exists("/tmp/ss459_smoke.db"):
    os.remove("/tmp/ss459_smoke.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
client.__enter__()  # اجرای startup (seed و ساخت جداول)
OK, FAIL = 0, 0


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


print("== Seed / Auth ==")
r = client.get("/api/auth/me")
check("auth/me", r.status_code == 200 and r.json()["username"] == "me")
today = r.json()["today"]
check("today jalali", today["jalali"].startswith("۱۴"), str(today))

r = client.get("/api/books")
check("3 books seeded", len(r.json()) == 3, str(r.json()))
chem = next(b for b in r.json() if b["title"] == "شیمی ۲")

r = client.get(f"/api/books/{chem['id']}/nodes")
ch1 = r.json()[0]
check("chemistry chapter tree", ch1["title"].startswith("فصل ۱"), ch1["title"])
titles = ch1["children"]
check("chapter → titles", len(titles) == 3)

r = client.get(f"/api/nodes/{titles[0]['id']}/test-sets")
tsets = r.json()
check("title has test set", len(tsets) >= 1)
ts = tsets[0]
check("36 questions in title test set", ts["question_count"] == 36, str(ts))

print("== Test engine: range + parity ==")
r = client.post("/api/test-sessions", json={
    "test_set_id": ts["id"], "count": 10, "parity": "odd",
    "sequence_from": 1, "sequence_to": 20, "timed": False})
check("session created", r.status_code == 200, r.text)
sid = r.json()["id"]
qs = r.json()["questions"]
check("all odd, in range, unique", all(q["sequence_no"] % 2 == 1 and 1 <= q["sequence_no"] <= 20 for q in qs)
      and len({q["id"] for q in qs}) == 10)

r = client.post("/api/test-sessions", json={
    "test_set_id": ts["id"], "count": 100, "parity": "odd",
    "sequence_from": 1, "sequence_to": 3})
check("insufficient error message exact", r.status_code == 422 and
      r.json()["detail"]["message"] == "فقط 2 سوال با این شرایط وجود دارد.", r.text)

print("== Answers / Finish / append-only ==")
for q in qs[:6]:
    rr = client.post(f"/api/test-sessions/{sid}/answers", json={
        "question_id": q["id"], "result": "correct", "answer": q["answer_key"]})
    assert rr.status_code == 200
for q in qs[6:8]:
    client.post(f"/api/test-sessions/{sid}/answers", json={
        "question_id": q["id"], "result": "wrong", "answer": "9"})
# 2 تا بی‌پاسخ می‌ماند → unanswered
r = client.post(f"/api/test-sessions/{sid}/finish")
res = r.json()
check("finish totals", res["total"] == 10 and res["correct"] == 6 and res["wrong"] == 2
      and res["unanswered"] == 2, json.dumps(res))
check("accuracy = 6/8", abs(res["accuracy"] - 0.75) < 1e-6)
check("needs duration input (untimed)", res["needs_duration_input"] is True)

r2 = client.post(f"/api/test-sessions/{sid}/finish")
check("finish idempotent", r2.json()["total"] == 10)
dup = client.post(f"/api/test-sessions/{sid}/answers", json={
    "question_id": qs[0]["id"], "result": "wrong"})
check("append-only in session", dup.status_code == 409 or dup.json().get("ok") is False, dup.text)

r = client.patch(f"/api/test-sessions/{sid}/duration", json={"actual_duration_minutes": 45})
check("untimed duration saved", r.json()["actual_duration_minutes"] == 45)

print("== Parity suggestion ==")
r = client.get(f"/api/nodes/{titles[0]['id']}/parity-state")
check("opposite parity suggested (odd→even)", r.json()["suggested_next"] == "even", r.text)

print("== Review queue ==")
r = client.get("/api/review/summary")
check("2 wrong + 2 unanswered in queue", r.json()["pending"] == 4, r.text)
r = client.post("/api/review-sessions")
check("review session built", r.status_code == 200, r.text)
rs = r.json()
check("review max 25", len(rs["questions"]) <= 25)
rid = rs["id"]
# اولین سوال را درست جواب بده → resolve + سکه
q0 = rs["questions"][0]
r = client.post(f"/api/review-sessions/{rid}/answers", json={
    "question_id": q0["id"], "result": "correct"})
check("review answer ok", r.json().get("ok") is True, r.text)
r = client.post(f"/api/review-sessions/{rid}/finish")
check("review finish", r.status_code == 200)

print("== Import (no coins) ==")
r = client.get("/api/rewards/summary")
coins_before = r.json()["coins"]
r = client.get(f"/api/nodes/{titles[1]['id']}/test-sets")
ts2 = r.json()[0]
r = client.post("/api/test-sessions/import", json={
    "test_set_id": ts2["id"],
    "answers": [{"question_id": i, "result": "correct"} for i in range(1, 11)],
    "date": today["iso"]})
check("import ok", r.status_code == 200, r.text)
r = client.get("/api/rewards/summary")
check("import gives no coins", r.json()["coins"] == coins_before,
      f"{coins_before} → {r.json()['coins']}")
r = client.get("/api/test-sessions?imported=true")
check("imported listed", len(r.json()) == 1)

print("== Rewards: wake-up / streak / coins ==")
r = client.post("/api/tasks", json={"title": "مرور جزوه شیمی", "task_type": "study",
                                    "date": today["iso"]})
check("manual task created", r.status_code == 200 and r.json()["source"] == "manual", r.text)
tid = r.json()["id"]
r = client.post(f"/api/tasks/{tid}/complete")
check("task completed", r.json()["status"] == "completed")
r = client.get("/api/rewards/summary")
check("streak day +1", r.json()["current_streak"] >= 1, r.text)
r = client.post("/api/rewards/wake-up")
check("wake-up recorded", r.json()["ok"] is True, r.text)

print("== Jalali week / planner ==")
ws = today["week_start"]
r = client.get(f"/api/planner/week/{ws}")
check("week has 7 days sat..fri", len(r.json()["days"]) == 7 and
      r.json()["days"][0]["weekday"] == "شنبه" and r.json()["days"][6]["weekday"] == "جمعه")
r = client.get(f"/api/planner/day/{today['iso']}")
check("day plan", r.status_code == 200 and "capacity_minutes" in r.json()["day_info"])

print("== Default classes seed ==")
r = client.post("/api/schedules/seed-defaults")
check("3 default classes", len(r.json()["created"]) == 3, r.text)

print("== Goals ==")
r = client.get(f"/api/nodes/{ch1['id']}/test-sets")
node_tsets = r.json()
r = client.post(f"/api/goals/weeks/{ws}", json={
    "items": [{"goal_type": "count", "target_value": 100},
              {"goal_type": "topic", "target_value": 30, "node_id": titles[0]["id"]}]})
check("goals saved", len(r.json()["items"]) == 2, r.text)

print("== V2.1: questionnaire adaptive ==")
r = client.post("/api/onboarding/questions/next")
check("first question", r.status_code == 200 and not r.json()["complete"], r.text)
answered = 0
for _ in range(45):
    r = client.post("/api/onboarding/questions/next")
    if r.json()["complete"]:
        break
    q = r.json()["question"]
    if q["type"] == "scale":
        ans = 3
    else:
        ans = q["options"][0]["key"]
    r2 = client.post("/api/onboarding/answers", json={
        "question_key": q["key"], "answer": ans})
    assert r2.status_code == 200, r2.text
    answered += 1
check("questionnaire ~40 answered", 30 <= answered <= 45, str(answered))
r = client.get("/api/user-model")
pers = r.json()["personality"]
check("personality dims with confidence", len(pers) == 10 and all(
    0 <= d["value"] <= 1 and 0 <= d["confidence"] <= 0.95 for d in pers.values()))
check("single answer didn't fix (confidence < max)", all(
    d["confidence"] <= 0.95 for d in pers.values()))

print("== V2.1: state / behavior ==")
r = client.post("/api/state/check-in", json={
    "energy": 3, "focus": 4, "motivation": 2, "stress": 3, "fatigue": 2, "sleep_hours": 7})
check("check-in ok", r.status_code == 200 and 0 <= r.json()["readiness"] <= 1, r.text)
r = client.get("/api/state/current")
check("state current", r.status_code == 200 and "confidence" in r.json(), r.text)
r = client.get("/api/behavior/features")
check("behavior features", "task_completion_rate" in r.json(), r.text)
r = client.get("/api/behavior/summary")
check("procrastination analysis", "pattern_detected" in r.json()["procrastination"])

print("== V2.1: weekly interview ==")
r = client.post(f"/api/planning/weekly-interview/start?week={ws}")
check("interview started", r.status_code == 200 and r.json()["total_count"] >= 15, r.text)
r = client.post(f"/api/planning/weekly-interview/{ws}/answer", json={
    "question_id": "priority_subject", "answer": "شیمی"})
check("interview answer", r.status_code == 200, r.text)
r = client.post(f"/api/planning/weekly-interview/{ws}/complete")
check("interview completed", r.json()["ok"] is True)

print("== V2.1: planning generate + manual override protection ==")
r = client.post("/api/planning/generate", json={"week_start": ws})
check("plan generated", r.status_code == 200 and len(r.json()["created_tasks"]) > 0, r.text)
gen = r.json()
check("explanations present", len(gen["explanations"]) == 7)
# یک Task دستی بساز، بعد rebuild — نباید حذف شود
r = client.post("/api/tasks", json={"title": "کار دستی مهم", "task_type": "study",
                                    "date": today["iso"]})
manual_id = r.json()["id"]
r = client.post("/api/planning/rebuild", json={"week_start": ws})
check("rebuild ok", r.status_code == 200)
r = client.get("/api/tasks")
check("manual task survives rebuild", any(t["id"] == manual_id for t in r.json()))
r = client.get(f"/api/planner/day/{today['iso']}")
day = r.json()
check("suggestions have reasons", all("reasons" in s for s in day["suggestions"]))

print("== V2.1: adaptation loop ==")
prev_week = (dt.date.fromisoformat(ws) - dt.timedelta(days=7)).isoformat()
r = client.post(f"/api/planning/evaluate?week={prev_week}")
check("evaluate ok", r.status_code == 200, r.text)

print("== V2: habits summary (قبل از ۳۰ روز محافظه‌کارانه) ==")
r = client.get("/api/habits/summary")
check("habit advice hidden before 30d", r.json()["past_threshold"] is False and
      r.json()["advice"] is None, r.text)

print("== Analytics: coverage ≠ accuracy ==")
r = client.get("/api/progress/overview")
ov = r.json()
check("overview stats", ov["total"] > 1000 and ov["volume"] >= 10, str(ov)[:200])
check("coverage separate from accuracy", "coverage" in ov and "accuracy" in ov)
r = client.get("/api/analytics/weaknesses")
check("weaknesses computed", r.status_code == 200)

print("== Split / merge ==")
r = client.post("/api/tasks", json={"title": "تست حسابان", "task_type": "test",
                                    "date": today["iso"], "question_count": 20})
stid = r.json()["id"]
r = client.post(f"/api/tasks/{stid}/split", json={"ratio": 0.5})
check("split", r.json()["first"]["question_count"] == 10 and
      r.json()["second"]["question_count"] == 10, r.text)
second_id = r.json()["second"]["id"]
r = client.post(f"/api/tasks/{stid}/merge", json={"other_task_id": second_id})
check("merge", r.json()["question_count"] == 20, r.text)

print("== School override ==")
r = client.post("/api/school-day-overrides", json={
    "date": today["iso"], "is_school_day": False, "reason": "تعطیل"})
check("override ok", r.status_code == 200)
r = client.get(f"/api/planner/day/{today['iso']}")
check("override boosts capacity ×1.35 (min 180)", r.json()["day_info"]["overridden"] is True
      and r.json()["day_info"]["capacity_minutes"] >= 180, str(r.json()["day_info"]))

print()
print(f"===== RESULT: {OK} passed, {FAIL} failed =====")
sys.exit(1 if FAIL else 0)
