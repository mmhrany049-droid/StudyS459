"""
Acceptance نسخه ۲.۲ — سند 11_ACCEPTANCE_TESTS_V2_2.md
اجرا:  cd backend && ../.venv/bin/python tests/test_acceptance_v2_2.py
"""
import io
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config as cfg  # noqa: E402

TEST_DIR = Path(__file__).resolve().parent / "_tmp"
if TEST_DIR.exists():
    shutil.rmtree(TEST_DIR)
TEST_DIR.mkdir(parents=True)
cfg.DATA_DIR = TEST_DIR
cfg.STORAGE_DIR = TEST_DIR / "storage"
cfg.STORAGE_DIR.mkdir()
cfg.DB_PATH = TEST_DIR / "test.db"
cfg.DATABASE_URL = f"sqlite:///{cfg.DB_PATH}"

import app.db as dbmod  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

dbmod.engine = create_engine(cfg.DATABASE_URL, connect_args={"check_same_thread": False})
dbmod.SessionLocal = sessionmaker(bind=dbmod.engine, autoflush=False, autocommit=False)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + (f"  -> {extra}" if extra and not cond else ""))


def find_leaf(tree):
    for n in tree:
        if not n["children"] and n["has_test_set"]:
            return n
        got = find_leaf(n["children"])
        if got:
            return got
    return None


def collect_leaves(tree, out):
    for n in tree:
        if not n["children"] and n["has_test_set"]:
            out.append(n)
        collect_leaves(n["children"], out)
    return out


with TestClient(app) as c:
    print("\n=== 0. bootstrap & books ===")
    r = c.get("/api/health").json()
    check("سرویس بالا است و نسخه ۲.۲ است", r["version"].startswith("2.2"), r)

    books = c.get("/api/books").json()
    check("سه کتاب seed شده‌اند", len(books) == 3, [b["title"] for b in books])
    check("حسابان ۱ نشر الگو موجود است", any(b["publisher"] == "نشر الگو" for b in books))
    check("شیمی ۲ مبتکران موجود است", any(b["publisher"] == "مبتکران" for b in books))
    check("فیزیک ۲ خیلی سبز موجود است", any(b["publisher"] == "خیلی سبز" for b in books))
    hes = next(b for b in books if "حسابان" in b["title"])
    check("حسابان سه سطح سختی دارد", hes["has_difficulty_levels"] is True)

    tree = c.get(f"/api/books/{hes['id']}/nodes").json()
    check("درخت حسابان ۵ فصل دارد", len(tree["nodes"]) == 5, len(tree["nodes"]))
    ch1 = tree["nodes"][0]
    check("فصل اول سه درس دارد", len(ch1["children"]) == 3)
    check("درس دوم ۷ بخش + کنکور دارد", len(ch1["children"][1]["children"]) == 8,
          len(ch1["children"][1]["children"]))

    node_id = find_leaf(tree["nodes"])["id"]

    print("\n=== 1. question bank ===")
    r = c.post(f"/api/nodes/{node_id}/questions/range", json={"from": 1, "to": 20}).json()
    check("ساخت بازه ۱ تا ۲۰ سوال", r["created"] == 20, r)

    lst = c.get(f"/api/nodes/{node_id}/questions").json()
    check("۲۰ سوال بدون جواب ساخته شد",
          lst["summary"]["total"] == 20 and lst["summary"]["missing_answer_key"] == 20)
    check("S3 خلاصه مبحث قبل از ورود پاسخ",
          {"total", "with_answer_key", "attempted", "coverage"} <= set(lst["summary"]))

    r = c.put(f"/api/nodes/{node_id}/questions/bulk", json={
        "items": [{"sequence_no": i, "answer_key": (i % 4) + 1} for i in range(1, 21)]}).json()
    check("ذخیره پاسخ‌نامه چهارگزینه‌ای ۲۰ سوال", r["updated"] == 20, r)

    c.post(f"/api/nodes/{node_id}/questions/range", json={"from": 21, "to": 25})
    r = c.put(f"/api/nodes/{node_id}/questions/bulk",
              json={"compact": "21:1, 22:2, 23:3, 24:4, 25:1"}).json()
    check("ورودی فشرده پاسخ‌نامه", r["updated"] == 5, r)

    lst = c.get(f"/api/nodes/{node_id}/questions").json()
    check("۲۵ سوال با کلید کامل", lst["summary"]["with_answer_key"] == 25)

    c.post(f"/api/nodes/{node_id}/questions/range", json={"from": 26, "to": 30})
    om = c.get(f"/api/nodes/{node_id}/questions?only_missing_key=true").json()
    check("S4 فیلتر «فقط بدون جواب»", len(om["questions"]) == 5, len(om["questions"]))
    ou = c.get(f"/api/nodes/{node_id}/questions?only_unattempted=true").json()
    check("S4 فیلتر «فقط بدون attempt»", len(ou["questions"]) == 30)

    qid = lst["questions"][0]["id"]
    r = c.patch(f"/api/questions/{qid}",
                json={"difficulty_level": 3, "question_tag": "محاسباتی"}).json()
    check("سطح سختی و برچسب نوع سوال (S7)", r["id"] == qid)

    print("\n=== 2. past attempt import by book ===")
    sheet = c.get(f"/api/books/{hes['id']}/answer-sheet").json()
    check("لیست بزرگ پاسخ فقط با انتخاب کتاب", sheet["total_questions"] == 25,
          sheet["total_questions"])
    check("گروه‌بندی با برچسب مبحث", "←" in sheet["groups"][0]["title"])

    qs = sheet["groups"][0]["questions"]
    answers = []
    for i, q in enumerate(qs):
        if i % 5 == 0:
            answers.append({"question_id": q["id"], "choice": None})
        elif i % 3 == 0:
            answers.append({"question_id": q["id"], "choice": (q["answer_key"] % 4) + 1})
        else:
            answers.append({"question_id": q["id"], "choice": q["answer_key"]})
    r = c.post("/api/attempts/import-by-book",
               json={"book_id": hes["id"], "answers": answers}).json()
    check("ورود گذشته ثبت شد", r["imported"] == 25, r)
    check("«نزده» جدا از غلط ثبت می‌شود",
          r["unanswered"] == 5 and r["wrong"] > 0 and r["correct"] > 0, r)
    check("Import سکه نمی‌دهد", r["coins_awarded"] == 0)
    check("موجودی سکه بعد از import صفر مانده",
          c.get("/api/rewards/summary").json()["coins"] == 0)

    queue = c.get("/api/review/queue").json()
    check("غلط و نزده وارد صف مرور شدند",
          queue["total"] == r["wrong"] + r["unanswered"], queue["total"])
    st = c.get(f"/api/nodes/{node_id}/questions").json()["summary"]
    check("Coverage/Accuracy بلافاصله به‌روز شد", st["attempted"] == 25 and st["accuracy"] > 0, st)

    print("\n=== 3. taught topics ===")
    leaves = collect_leaves(tree["nodes"], [])
    empty_node = next(x for x in leaves if x["id"] != node_id)
    c.post("/api/taught-topics", json={"node_id": node_id, "source_type": "school",
                                       "notes": "جلسه امروز"})
    c.post("/api/taught-topics", json={"node_id": empty_node["id"],
                                       "source_type": "external_class"})
    ins = c.get("/api/taught-topics/insights").json()
    check("مبحث تدریس‌شده در insights می‌آید", ins["counts"]["total"] == 2, ins["counts"])
    check("S10 هشدار «تدریس‌شده بدون بانک تست»",
          any("بانک تست ندارد" in w for w in ins["warnings"]), ins["warnings"])
    check("وضعیت هر مبحث محاسبه می‌شود",
          all(i["status"] in ("no_bank", "under_practiced", "weak", "good") for i in ins["items"]))

    c.post(f"/api/nodes/{empty_node['id']}/questions/range", json={"from": 1, "to": 12})
    c.put(f"/api/nodes/{empty_node['id']}/questions/bulk",
          json={"compact": ",".join(f"{i}:{(i % 4) + 1}" for i in range(1, 13))})
    ins = c.get("/api/taught-topics/insights").json()
    check("تست نزده همان مبحث پیشنهاد می‌شود",
          any(s["node_id"] == empty_node["id"] for s in ins["suggestions"]), ins["suggestions"])

    print("\n=== 4. exams: media + multi attempt ===")
    exam_id = c.post("/api/exams", json={"title": "امتحان میان‌ترم حسابان",
                                         "exam_kind": "school",
                                         "total_questions": 10}).json()["id"]
    r = c.post(f"/api/exams/{exam_id}/files",
               files={"file": ("exam.pdf", io.BytesIO(b"%PDF-1.4\nfake"), "application/pdf")},
               data={"file_kind": "exam_paper"})
    check("آپلود PDF صورت امتحان", r.status_code == 200 and r.json()["file_type"] == "pdf", r.text)
    r = c.post(f"/api/exams/{exam_id}/files",
               files={"file": ("key.png", io.BytesIO(b"\x89PNG" + b"0" * 100), "image/png")},
               data={"file_kind": "answer_key_sheet"})
    check("S8 پاسخ‌نامه رسمی جدا از صورت امتحان",
          r.status_code == 200 and r.json()["file_kind"] == "answer_key_sheet", r.text)
    r = c.post(f"/api/exams/{exam_id}/files",
               files={"file": ("big.png", io.BytesIO(b"0" * (6 * 1024 * 1024)), "image/png")})
    check("S12 محدودیت حجم فایل با پیام واضح",
          r.status_code == 400 and "حجم" in r.json()["detail"], r.text)

    r = c.put(f"/api/exams/{exam_id}/answer-key",
              json={"compact": "1 2 3 4 1 2 3 4 1 2"}).json()
    check("ثبت پاسخ‌نامه رسمی امتحان", r["saved"] == 10, r)

    KEY = (1, 2, 3, 4, 1, 2, 3, 4, 1, 2)
    a1 = c.post(f"/api/exams/{exam_id}/attempts", json={
        "label": "نوبت اول", "duration_minutes": 55,
        "answers": [{"sequence_no": i, "user_answer": KEY[i - 1] if i <= 5 else None}
                    for i in range(1, 11)]}).json()
    check("نوبت اول با مدت زمان",
          a1["correct"] == 5 and a1["unanswered"] == 5 and a1["duration_minutes"] == 55, a1)
    a2 = c.post(f"/api/exams/{exam_id}/attempts", json={
        "label": "نوبت دوم", "duration_minutes": 40,
        "answers": [{"sequence_no": i, "user_answer": KEY[i - 1]} for i in range(1, 11)]}).json()
    check("نوبت دوم ۱۰۰٪", a2["percentage"] == 100.0, a2)

    detail = c.get(f"/api/exams/{exam_id}").json()
    check("چند نوبت روی یک امتحان", len(detail["attempts"]) == 2)
    check("S9 مقایسه نوبت‌ها (درصد و زمان)",
          detail["progress"]["delta_percentage"] == 50.0
          and detail["progress"]["delta_minutes"] == -15, detail["progress"])

    print("\n=== 5. mock multi-subject ===")
    subjects = {b["subject"]: b["subject_id"] for b in books}
    mock_id = c.post("/api/exams", json={"title": "آزمون آزمایشی جامع",
                                         "exam_kind": "mock"}).json()["id"]
    r = c.put(f"/api/exams/{mock_id}/sections", json={"sections": [
        {"subject_id": subjects["شیمی"], "sequence_from": 1, "sequence_to": 30,
         "duration_minutes": 35},
        {"subject_id": subjects["حسابان"], "sequence_from": 31, "sequence_to": 55,
         "duration_minutes": 45},
        {"subject_id": subjects["فیزیک"], "sequence_from": 56, "sequence_to": 80,
         "duration_minutes": 40}]}).json()
    check("بخش‌بندی ۳۰ شیمی / ۲۵ حسابان / ۲۵ فیزیک", r["sections"] == 3, r)
    r = c.put(f"/api/exams/{mock_id}/topic-map", json={"items": [
        {"sequence_from": 31, "sequence_to": 40, "node_id": node_id},
        {"sequence_from": 41, "sequence_to": 55, "node_id": empty_node["id"]}]}).json()
    check("نگاشت بازه شماره سوال به مبحث", r["mapped"] == 25, r)

    c.put(f"/api/exams/{mock_id}/answer-key",
          json={"compact": " ".join(str((i % 4) + 1) for i in range(1, 81))})
    c.post(f"/api/exams/{mock_id}/attempts", json={
        "label": "اجرای اول", "duration_minutes": 120,
        "answers": [{"sequence_no": i, "user_answer": ((i % 4) + 1) if i % 2 == 0 else None}
                    for i in range(1, 81)]})
    an = c.get(f"/api/exams/{mock_id}/analysis").json()
    check("نتیجه per subject", len(an["per_subject"]) == 3, an["per_subject"])
    check("نتیجه per topic", len(an["per_topic"]) == 2, an["per_topic"])
    check("زمان per بخش ذخیره شد", all(s["duration_minutes"] for s in an["per_subject"]))

    print("\n=== 6. exam readiness ===")
    exam_day = date.today() + timedelta(days=10)
    ue = c.post("/api/upcoming-exams", json={
        "title": "امتحان نهایی فصل ۱", "exam_date": exam_day.isoformat(),
        "node_ids": [node_id, empty_node["id"]]}).json()
    sug = c.get(f"/api/upcoming-exams/{ue['id']}/suggested-tasks").json()
    check("پیشنهاد تست از مباحث امتحان", len(sug["suggestions"]) >= 1, sug)
    check("پیشنهاد فقط از بانک همان مباحث",
          all(s["node_id"] in (node_id, empty_node["id"]) for s in sug["suggestions"]))
    check("S6 حالت «۱۴ روز مانده»",
          sug["countdown_mode"] and sug["upcoming_exam"]["days_left"] == 10, sug)
    check("درصد مباحث Coverage پایین", "low_coverage_ratio" in sug)
    check("تاریخ امتحان شمسی", "/" in sug["upcoming_exam"]["exam_date_jalali"])
    wo = c.get(f"/api/upcoming-exams/{ue['id']}/suggested-tasks?wrong_only=true").json()
    check("فیلتر «فقط غلط‌ها»", all(s["open_review"] > 0 for s in wo["suggestions"]))

    r = c.post(f"/api/upcoming-exams/{ue['id']}/materialize").json()
    check("Task آمادگی امتحان ساخته می‌شود", r["created"] >= 1, r)
    prep = [t for t in c.get("/api/tasks").json() if t["task_type"] == "exam_prep"]
    check("Task آمادگی deadline تاریخ امتحان دارد",
          bool(prep) and prep[0]["due_at"] == exam_day.isoformat(), prep)

    print("\n=== 7. no regression: V1 / V2 / V2.1 ===")
    ps = c.get(f"/api/nodes/{node_id}/parity-state").json()
    check("V1 parity state", "suggested_parity" in ps)
    s = c.post("/api/test-sessions", json={"node_id": node_id, "count": 5,
                                           "sequence_from": 1, "sequence_to": 20,
                                           "parity": "odd"})
    check("V1 جلسه با Range + parity فرد", s.status_code == 200, s.text)
    sess = s.json()
    check("V1 فقط شماره‌های فرد", all(q["sequence_no"] % 2 == 1 for q in sess["questions"]))
    bad = c.post("/api/test-sessions", json={"node_id": node_id, "count": 999, "parity": "even"})
    check("V1 پیام دقیق در کمبود سوال",
          bad.status_code == 400 and "فقط" in bad.json()["detail"], bad.text)

    fin = c.post(f"/api/test-sessions/{sess['id']}/finish", json={
        "answers": [{"question_id": q["question_id"], "answer": 1}
                    for q in sess["questions"][:3]],
        "actual_duration_minutes": 12}).json()
    check("V1 correct/wrong/unanswered جدا",
          fin["correct"] + fin["wrong"] + fin["unanswered"] == 5, fin)
    check("V2 مدت واقعی جلسه Untimed", fin["duration_minutes"] == 12)
    check("V1 finish idempotent",
          c.post(f"/api/test-sessions/{sess['id']}/finish",
                 json={"answers": []}).json()["total"] == 5)
    rw2 = c.get("/api/rewards/summary").json()
    check("V2 سکه پاسخ درست + streak", rw2["coins"] > 0 and rw2["current_streak"] >= 1, rw2)

    r = c.post("/api/rewards/wake-up", json={"time": "06:40"}).json()
    check("V2 بیدار شدن قبل ۰۶:۴۵ → ۲۰ سکه", r["points"] == 20, r)
    check("V2 بیدار شدن یک‌بار در روز",
          c.post("/api/rewards/wake-up", json={"time": "06:40"}).json()["already"] is True)

    rev = c.post("/api/review-sessions")
    check("V2 جلسه مرور خوشه‌ای", rev.status_code == 200, rev.text)
    check("V2 سقف ۲۵ سوال مرور", len(rev.json()["questions"]) <= 25)

    sch = c.get("/api/schedules").json()
    check("V2 سه کلاس تقویتی پیش‌فرض", len(sch) == 3, sch)
    check("V2 source=default_seed_v2", all(x["source"] == "default_seed_v2" for x in sch))

    dash = c.get("/api/dashboard").json()
    check("V2 تاریخ شمسی داشبورد", "/" in dash["today"]["jalali"])
    check("V2 هفته از شنبه", "شنبه" in dash["week"]["label"])
    check("V2 ظرفیت روز", dash["capacity"]["capacity_minutes"] > 0)
    check("V2 فاز یادگیری ۳۰ روزه",
          dash["habit"]["threshold"] == 30 and dash["habit"]["learning_phase"] is True)
    check("V2.2 کارت پوشش امتحانات هفته", bool(dash["exam_coverage_card"]["items"]))

    stt = c.post("/api/state/check-in", json={"energy": 0.8, "focus": 0.7, "motivation": 0.6,
                                              "stress": 0.3, "fatigue": 0.2}).json()
    check("V2.1 State Engine با confidence", "confidence" in stt and stt["readiness"] > 0.5, stt)
    check("V2.1 Behavior features", "evidence_count" in c.get("/api/behavior/features").json())
    check("V2.1 مصاحبه هفتگی",
          c.post("/api/planning/weekly-interview",
                 json={"answers": {"capacity": "متوسط"}, "complete": True}).json()["completed"])

    gen = c.post("/api/planning/generate").json()
    check("V2.1 Planner با توضیح", "explanation" in gen and gen["target_tasks"] >= 1, gen)

    t = c.post("/api/tasks", json={"title": "کار دستی من", "task_type": "study",
                                   "quantity": 1}).json()
    check("V2.1 Task دستی", t["source_type"] == "manual" and t["manual_override"])
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    check("V2.1 جابه‌جایی Task",
          c.post(f"/api/tasks/{t['id']}/move",
                 json={"planned_date": tomorrow}).json()["planned_date"] == tomorrow)
    check("V2.1 split کردن Task",
          len(c.post(f"/api/tasks/{t['id']}/split", json={"parts": 3}).json()["parts"]) == 3)
    c.patch(f"/api/tasks/{t['id']}", json={"status": "completed"})
    check("V2.1 تکمیل Task غیرتست سکه می‌دهد",
          c.get("/api/rewards/summary").json()["coins"] > rw2["coins"])

    print("\n=== 8. S9 soft delete + S11 export + S2 draft ===")
    c.post(f"/api/nodes/{node_id}/questions/range", json={"from": 31, "to": 31})
    fresh_q = [q for q in c.get(f"/api/nodes/{node_id}/questions").json()["questions"]
               if q["sequence_no"] == 31][0]
    check("سوال بدون history واقعاً حذف می‌شود",
          c.delete(f"/api/questions/{fresh_q['id']}").json()["soft_deleted"] is False)
    used = [q for q in c.get(f"/api/nodes/{node_id}/questions").json()["questions"]
            if q["attempt_count"] > 0][0]
    check("S9 سوال دارای history آرشیو نرم می‌شود",
          c.delete(f"/api/questions/{used['id']}").json()["soft_deleted"] is True)

    exp = c.get(f"/api/books/{hes['id']}/export").json()
    check("S11 خروجی JSON بانک",
          exp["format_version"] == "ss459-bank-1.0" and len(exp["exported_sets"]) >= 1)

    c.put("/api/drafts", json={"scope": "import_book:1", "payload": {"1": 2, "2": None}})
    check("S2 Auto-save draft",
          c.get("/api/drafts/import_book:1").json()["payload"] == {"1": 2, "2": None})

    prog = c.get("/api/progress/overview").json()
    check("Progress: Coverage و Accuracy جدا",
          all({"coverage", "accuracy"} <= set(b) for b in prog["books"]))
    check("Progress: روند ۱۴ روزه شمسی", len(prog["trend"]) == 14)

print("\n" + "=" * 60)
print(f"نتیجه: {len(PASS)} قبول / {len(FAIL)} مردود")
if FAIL:
    for f in FAIL:
        print("  FAIL", f)
    sys.exit(1)
print("همه Acceptanceهای نسخه ۲.۲ پاس شدند")
