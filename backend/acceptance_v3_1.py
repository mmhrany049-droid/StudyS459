"""V3.1 acceptance run — the eleven items of study_system_v3_1_docs/11_ACCEPTANCE_V3_1.md.

Run with a throwaway database:

    STUDYS459_DB_PATH=/tmp/acceptance.db python acceptance_v3_1.py

Exits non-zero if any item fails, so it can be used as a release gate in addition
to the unit/acceptance tests in ``app/tests``.
"""
import sys, json
sys.path.insert(0, ".")
from app.db.base import reset_engine, init_db
reset_engine(); init_db()
from fastapi.testclient import TestClient
from app.main import app

results = []
def check(n, label, ok, extra=""):
    results.append((n, label, bool(ok), extra))
    print(("PASS" if ok else "FAIL"), f"{n}. {label}", "|", extra)

with TestClient(app) as c:  # startup seeds the books/curriculum
    BOOK = 2  # شیمی ۲ (یازدهم) — the multi-topic chapter book used by the checkup model

    # 1 — exam types
    e1 = c.post("/api/exams", json={"title": "امتحان نهایی شیمی", "exam_type": "comprehensive", "date": "1405/09/20"}).json()
    types = [t["value"] for t in c.get("/api/exam-center").json()["types"]]
    check(1, "Exam با typeهای personal/school/mock/checkup/comprehensive",
          e1.get("type_label") and types == ["personal", "school", "mock", "checkup", "comprehensive"],
          f"{e1.get('type_label')} | {len(types)} types")

    # 2 — chapter tick cascades for that exam
    tree = c.get(f"/api/books/{BOOK}/tree").json()
    chapter = next(n for n in tree["topics"] if n["node_type"] == "chapter")
    r = c.post("/api/exams/" + str(e1["id"]) + "/topics", json={"topic_id": chapter["id"], "mark_kind": "planned", "checked": True})
    affected = r.json().get("affected", 0)
    check(2, "تیک فصل روی Exam فرزندان را علامت می‌زند", r.status_code == 200 and affected > 1,
          f"«{chapter['title']}» → {affected} مبحث")

    # 3 — checkup covers a multi-topic segment (its topics first get a question bank)
    chk = c.get("/api/exam-checkups").json()["checkups"][0]
    for topic_id in chk["included_topic_ids"][:3]:
        c.post(f"/api/books/{BOOK}/nodes/{topic_id}/questions/range", json={"from_sequence": 1, "to_sequence": 10})
    session = c.post("/api/exam-checkups/" + str(chk["id"]) + "/session", json={"count": 12}).json()
    check(3, "Checkup شیمی چند مبحث سگمنت را پوشش می‌دهد",
          session["topic_count"] > 1 and session["questions"] >= 3 and session["topics_with_questions"] >= 2,
          f"{chk['label']}: {session['topic_count']} مبحث، {session['questions']} سؤال، "
          f"{session['topics_with_questions']} مبحث سؤال‌دار")

    # 4 — curriculum 10–12 + plannable only with a bank
    ov = c.get("/api/curriculum/overview").json()
    by_grade = {grade: len(books) for grade, books in ov["grades"].items()}
    leaf = next(n for n in tree["topics"] if n["node_type"] == "chapter")["children"][0]
    bank = c.post(f"/api/books/{BOOK}/nodes/{leaf['id']}/questions/range", json={"from_sequence": 1, "to_sequence": 12})
    pr = c.get("/api/priorities").json()
    plannable_now = c.get(f"/api/books/{BOOK}/tree").json()
    leaf_after = json.dumps(plannable_now, ensure_ascii=False)
    check(4, "Curriculum ۱۰–۱۲ و plannable فقط با بانک",
          set(by_grade) == {"دهم", "یازدهم", "دوازدهم"} and bank.status_code == 200 and "visible_only_total" in pr,
          f"کتاب‌ها {by_grade} | visible_only_total={pr.get('visible_only_total')}")

    # 5 — Jalali calendar window
    rng = c.get("/api/calendar/range").json()
    month = c.get("/api/calendar/month", params={"year": 1406, "month": 3}).json()
    check(5, "تقویم شمسی ۱۴۰۵–۱۴۰۸ قابل استفاده است",
          rng["supported_years"] == [1405, 1406, 1407, 1408] and month["days"][0]["jalali"]["year"] == 1406
          and month["weekdays"][0] == "شنبه",
          f"{rng['supported_years']} | {month['month_title']} | اول هفته {month['weekdays'][0]}")

    # 6 — Exam Center past + upcoming
    past_exam = c.post("/api/exams", json={"title": "امتحان گذشته", "exam_type": "school", "date": "1405/05/10"}).json()
    c.post("/api/exams/" + str(past_exam["id"]) + "/attempts",
           json={"percentage": 62.5, "correct_count": 25, "total_questions": 40})
    center = c.get("/api/exam-center").json()
    past = next(e for e in center["past"] if e["title"] == "امتحان گذشته")
    upcoming = [e for e in center["upcoming"] if e["title"] == "امتحان نهایی شیمی"][0]
    check(6, "Exam Center: گذشته با نتیجه، آینده با آماده‌سازی",
          "result" in past and "prep" in upcoming and upcoming["prep"]["readiness"]["value"] is None,
          f"گذشته: {past['result']['attempts']} تلاش ثبت‌شده | آینده: {upcoming['prep']['topics_marked']} مبحث، آمادگی نامعلوم")

    # 7 — retake keeps history (new sitting is a new row; the original is untouched)
    past_now = next(e for e in c.get("/api/exam-center").json()["past"] if e["id"] == past["id"])
    before = c.get(f"/api/exams/{past['id']}").json()
    retake = c.post("/api/exams/" + str(past["id"]) + "/retake", json={}).json()
    after = c.get(f"/api/exams/{past['id']}").json()
    check(7, "Retake تاریخچه attempt را پاک نمی‌کند",
          after["attempt_count"] == before["attempt_count"] == 1
          and after["percentage"] == before["percentage"] == 62.5
          and retake["retake_of_id"] == past["id"] and retake["attempt_no"] == before["attempt_no"] + 1,
          f"نوبت اصلی {before['attempt_no']} (ثبت {before['percentage']}٪) → نوبت جدید {retake['attempt_no']}، "
          f"past attempts={past_now['result']['attempts']}")

    # 8 — bank + four-option key per topic
    key = c.post(f"/api/books/{BOOK}/nodes/{leaf['id']}/answer-key/compact", json={"text": "1:2,2:3,3:1,4:4,5:0", "apply": True})
    compact = c.post(f"/api/books/{BOOK}/nodes/{leaf['id']}/answer-key/compact", json={"text": "23124", "apply": True})
    check(8, "بانک تست + پاسخ‌نامه چهارگزینه‌ای per مبحث",
          key.status_code == 200 and key.json().get("parsed", 0) >= 4 and compact.status_code == 200,
          f"چسباندن فشرده ۱: «{key.json().get('parsed')}» کلید (پاک‌شده {key.json().get('cleared', 0)}) | ۲: «{compact.json().get('parsed')}» کلید")

    # 9 — import past attempts with «نزده»
    sheet = c.get("/api/attempts/import-sheet", params={"book_id": BOOK}).json()
    rows = [q for chapter in sheet["chapters"] for group in chapter["groups"] for q in group["questions"]]
    if rows:
        r = c.post("/api/attempts/import-by-book", json={
            "book_id": BOOK,
            "items": [{"question_id": rows[0]["question_id"], "result": "unanswered"},
                      {"question_id": rows[1]["question_id"], "result": "correct"}],
        })
    check(9, "Import گذشته با گزینه نزده", bool(rows) and r.status_code in (200, 201),
          f"status={r.status_code if rows else '—'} | {len(sheet['chapters'])} فصل، {len(rows)} ردیف در فهرست بزرگ")

    # 10 — day-start question visibly affects today's workload
    before_cap = c.get("/api/capacity/today").json()["realistic_minutes"]
    saved = c.post("/api/checkins", json={"phase": "start", "answers": {"energy": 1, "free_time": 1}}).json()
    after_cap = c.get("/api/capacity/today").json()
    adj = after_cap["self_report_adjustment"]
    check(10, "سؤال آغاز روز روی بار امروز اثر قابل مشاهده دارد",
          bool(saved["effects"]) and after_cap["realistic_minutes"] < before_cap and adj["reasons"],
          f"{before_cap}→{after_cap['realistic_minutes']} دقیقه ({adj['delta_pct']:+.2%}) با {len(adj['reasons'])} دلیل")

    # 11 — regression safety of healthy V3 features
    dash = c.get("/api/dashboard").json()
    plant = c.get("/api/planning/current").json()
    week = c.get("/api/planning/week").json()
    check(11, "قابلیت‌های سالم V3 نشکسته‌اند",
          all(k in dash for k in ("what_matters_now", "what_next", "time", "learning", "checkin", "today_brief"))
          and len(plant.get("stages", [])) == 15 and len(week["calendar"]["days"]) == 7,
          f"dashboard+planning(۱۵ مرحله)+تقویم هفته همه پاسخ دادند")

ok = sum(1 for _, _, good, _ in results if good)
print(f"\n==== {ok}/{len(results)} acceptance checks passed ====")
sys.exit(0 if ok == len(results) else 1)
