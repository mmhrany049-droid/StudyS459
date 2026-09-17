"""End-to-end smoke test of the V3 loop through the HTTP API.

INPUT → MODEL → DECIDE → PLAN → EXECUTE → OBSERVE → LEARN → REPLAN

Run with:  STUDYS459_DB_PATH=/tmp/e2e.db python e2e_smoke.py
"""

from __future__ import annotations

import json
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from app.main import app  # noqa: E402

c = TestClient(app)
FAILED: list[str] = []


def show(label: str, r, keys=None, limit=460):
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    if keys and isinstance(body, dict):
        body = {k: body.get(k) for k in keys if k in body}
    tag = "OK " if r.status_code < 400 else "ERR"
    if r.status_code >= 400:
        FAILED.append(f"{label} -> {r.status_code}")
    print(f"{tag} {label}: {r.status_code} {json.dumps(body, ensure_ascii=False, default=str)[:limit]}")
    return body


def find_leaf(nodes):
    for n in nodes:
        if n["is_leaf"]:
            return n
        got = find_leaf(n["children"])
        if got:
            return got
    return None


with c:
    print("\n=== 1. INPUT / bootstrap ===")
    show("bootstrap", c.post("/api/bootstrap"), ["date_long", "week_label", "books", "onboarding"])
    books = c.get("/api/books").json()
    books = books["books"] if isinstance(books, dict) else books
    calc = next(b for b in books if "حسابان" in b["title"])
    print("   books:", [(b["id"], b["title"], b["topic_count"]) for b in books])

    print("\n=== 2. MODEL: taught cascade + answer key + question bank ===")
    tree = c.get(f"/api/books/{calc['id']}/tree").json()
    ch = tree["topics"][0]
    show("taught cascade", c.post(f"/api/topics/{ch['id']}/taught", json={"taught": True, "cascade": True}),
         ["affected_count", "taught_state", "indeterminate"])
    leaf = find_leaf(tree["topics"])
    print("   leaf:", leaf["id"], leaf["title"])
    show("add range", c.post(f"/api/books/{calc['id']}/nodes/{leaf['id']}/questions/range",
                             json={"seq_from": 1, "seq_to": 24, "level": 2}), ["created", "skipped"])
    show("bulk answer key", c.put(f"/api/books/{calc['id']}/nodes/{leaf['id']}/answer-key",
                                  json={"items": [{"sequence_no": i, "answer_key": str((i % 4) + 1)} for i in range(1, 25)]}),
         ["updated", "invalid"])
    show("compact keys", c.post(f"/api/books/{calc['id']}/nodes/{leaf['id']}/answer-key/compact",
                                json={"text": "1:2,2:3,3:1,4:4", "start_sequence": 25}), ["parsed", "updated"])

    print("\n=== 3. DECIDE: priority + recommendation with explanation ===")
    show("priorities", c.get("/api/priorities?explain=true&limit=4"), ["weights"])
    recs = c.get("/api/recommendations").json()["recommendations"]
    print("   recommendations:", len(recs))
    if recs:
        rid = recs[0]["id"]
        show("explain rec", c.get(f"/api/recommendations/{rid}/explain"),
             ["intervention", "question_count", "what", "why", "evidence", "what_can_i_change"])

    print("\n=== 4. PLAN: adaptive interview → weekly plan ===")
    ps = c.post("/api/planning/sessions", json={}).json()
    sid = ps["id"]
    print("   planning session:", sid, "| status:", ps.get("status"))
    for _ in range(8):
        q = c.get(f"/api/planning/sessions/{sid}/questions").json()
        question = q.get("question")
        if not question:
            break
        print("   Q:", question["code"], "|", question["text"][:60])
        ans = {"code": question["code"], "answer": question["options"][0]["value"] if question.get("options") else True}
        r = c.post(f"/api/planning/sessions/{sid}/answers", json=ans)
        if r.status_code >= 400:
            show("answer question", r)
            break
    show("generate plan", c.post(f"/api/planning/sessions/{sid}/generate"), ["task_count", "week_label", "overload"])
    plan = c.get("/api/planning/week").json()
    print("   week tasks:", len(plan.get("days", [])), "days |", plan.get("summary", {}))
    show("explanation", {"json": lambda: plan.get("explanation", {}), "status_code": 200}.__class__.__name__ and
         c.get("/api/planning/current"), ["explanation", "status"])

    print("\n=== 5. EXECUTE: test session with ANSWERED / UNANSWERED / NOT_ENTERED ===")
    show("pool", c.get(f"/api/test-engine/pool?topic_id={leaf['id']}&count=10"), ["available", "enough"])
    s = c.post("/api/test-sessions", json={"book_id": calc["id"], "topic_id": leaf["id"], "count": 10, "start_now": True}).json()
    tcid = s["id"]
    print("   session:", tcid, "| questions:", len(s["questions"]), "| planned:", s.get("planned_duration_label"))
    entries = []
    for i, q in enumerate(s["questions"]):
        if i < 5:
            entries.append({"question_id": q["question_id"], "selected_choice": str((i % 4) + 1), "state": "ANSWERED"})
        elif i < 8:
            entries.append({"question_id": q["question_id"], "state": "UNANSWERED"})
    show("save entries (draft)", c.post(f"/api/test-sessions/{tcid}/entries", json=entries),
         ["saved", "states_summary"])
    show("submit + duration", c.post(f"/api/test-sessions/{tcid}/submit",
                                     json={"entries": [], "actual_duration_minutes": 38}),
         ["status", "total", "correct", "wrong", "unanswered", "not_entered", "accuracy", "invariant_ok"])
    show("result", c.get(f"/api/test-sessions/{tcid}/result"),
         ["total", "correct", "wrong", "unanswered", "not_entered", "accuracy", "duration_label"])

    print("\n=== 6. OBSERVE / LEARN: learning state, review, analytics ===")
    show("topic state", c.get(f"/api/learning/state/{leaf['id']}"),
         ["accuracy", "coverage", "confidence", "uncertainty", "readiness", "diagnosis_hint"])
    show("review build", c.post("/api/review/build", json={}), ["created", "queue_size"])
    show("review queue", c.get("/api/review/queue"), ["total", "critical", "items"])
    show("overview", c.get("/api/progress/overview"), ["totals", "weaknesses"])
    show("weaknesses", c.get("/api/analytics/weaknesses?limit=3"), ["items"])
    show("behaviour summary", c.get("/api/behavior/summary"), ["features", "patterns", "state"])
    show("user model", c.get("/api/user-model"), ["personality", "confidence"])

    print("\n=== 7. EXAM + GOAL (first class) ===")
    show("create exam", c.post("/api/exams", json={"title": "امتحان نوبت اول", "exam_type": "school",
                                                   "date": "1405/08/15", "subject_id": calc.get("subject_id")}),
         ["id", "title", "date_label", "days_remaining"])
    show("create mock", c.post("/api/exams", json={"title": "آزمون آزمایشی ۱", "exam_type": "mock",
                                                   "date": "1405/07/10"}), ["id", "title", "exam_type"])
    show("exam calendar", c.get("/api/exams/calendar"), ["upcoming"])
    show("create goal", c.post("/api/goals", json={"title": "تسلط بر حسابان تا دی", "goal_type": "mastery",
                                                   "target_date": "1405/10/01", "book_ids": [calc["id"]]}),
         ["id", "title", "progress", "target_date_label"])
    show("goal refresh", c.post(f"/api/goals/1/refresh"), ["progress", "milestones"])
    show("goals list", c.get("/api/goals"), ["goals"])

    print("\n=== 8. IMPORT: historical past attempts (book → big list → 1..4/نزده) ===")
    sheet = c.get(f"/api/attempts/import-sheet?book_id={calc['id']}").json()
    print("   sheet groups:", len(sheet.get("chapters", [])),
          "| rows:", sum(len(g["questions"]) for ch in sheet.get("chapters", []) for g in ch.get("groups", [])))
    rows = [(g, r) for ch in sheet.get("chapters", []) for g in ch.get("groups", []) for r in g["questions"]][:6]
    items = []
    for i, (_g, r) in enumerate(rows):
        items.append({"question_id": r["question_id"], "choice": str((i % 4) + 1)} if i % 3 else
                     {"question_id": r["question_id"], "unanswered": True})
    if items:
        show("import attempts", c.post("/api/attempts/import-by-book",
                                       json={"book_id": calc["id"], "items": items, "date": "1405/06/01"}),
             ["created", "duplicate", "session_id", "summary"])
    show("import summary", c.get("/api/attempts/import-summary"), ["imports", "totals"])

    print("\n=== 9. RECALC / INTEGRITY ===")
    show("change answer key (correction)", c.put(f"/api/questions/1/answer-key", json={"answer_key": "3", "reason": "تصحیح"}),
         ["changed", "previous", "recalc_required"])
    show("recalculate", c.post("/api/recalculations", json={"scope": "user", "trigger": "manual"}), ["jobs", "scope"])
    show("integrity", c.get("/api/integrity/report"), ["ok", "issues", "checked"])

    print("\n=== 10. EXPERIMENTS + EXPLAINABILITY + CAPACITY ===")
    show("experiments", c.get("/api/experiments"), ["experiments", "templates"])
    exp = c.post("/api/experiments", json={"template_key": "warmup_easy_before_hard",
                                           "title": "گرم‌کردن با سؤال آسان"}).json()
    print("   experiment:", exp)
    show("capacity today", c.get("/api/capacity/today"), ["theoretical_minutes", "realistic_minutes", "explanation"])
    show("duration estimate", c.get("/api/duration/estimate?task_type=test_session&question_count=10"), ["low", "high", "method", "confidence"])
    show("dashboard", c.get("/api/dashboard"),
         ["what_matters", "next_action", "why", "time", "exams", "goals"])

print("\n" + "=" * 70)
print("FAILURES:", FAILED if FAILED else "none 🎉")
print("=" * 70)
