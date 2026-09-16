"""
پرسش‌نامه تطبیقی — اسناد 14 و 15 و 22 نسخه ۲.۱
اجرا:  cd backend && ../.venv/bin/python tests/test_questionnaire_v2_1.py
"""
import sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config as cfg
base = Path(__file__).resolve().parent / "_tmp_questionnaire"
shutil.rmtree(base, ignore_errors=True); base.mkdir(parents=True)
cfg.DATA_DIR = base; cfg.STORAGE_DIR = base/"storage"; cfg.STORAGE_DIR.mkdir()
cfg.DB_PATH = base/"t.db"; cfg.DATABASE_URL = f"sqlite:///{cfg.DB_PATH}"
import app.db as dbm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
dbm.engine = create_engine(f"sqlite:///{cfg.DB_PATH}", connect_args={"check_same_thread": False})
dbm.SessionLocal = sessionmaker(bind=dbm.engine, autoflush=False, autocommit=False)
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app); c.__enter__()

ok=fail=0
def chk(n,cond,extra=""):
    global ok,fail
    if cond: ok+=1; print("  OK  ",n)
    else: fail+=1; print("  FAIL",n,extra)

p=c.get("/api/questionnaire/profile").json()
chk("پروفایل اولیه: ۱۰ بُعد سند ۱۴", len(p["traits"])==10, str(len(p["traits"])))
chk("اطمینان اولیه صفر", p["overall_confidence"]==0.0, str(p["overall_confidence"]))
chk("همه ابعاد در ۰.۵ خنثی", all(t["value"]==0.5 for t in p["traits"]))
chk("هیچ بُعدی قابل‌اتکا نیست", all(not t["reliable"] for t in p["traits"]))
chk("disclaimer وجود دارد", "تشخیص" in p["disclaimer"])

q=c.get("/api/questionnaire/next").json()["question"]
chk("سوال اول ارائه می‌شود", q is not None and "text" in q)
first=q["code"]

# یک پاسخ افراطی: اهمال‌کاری بالا
c.post("/api/onboarding/answers", json={"question_code":"q_start_delay","answer_value":"5"})
p=c.get("/api/questionnaire/profile").json()
pr=[t for t in p["traits"] if t["key"]=="procrastination"][0]
chk("یک پاسخ ویژگی را قطعی نمی‌کند (shrinkage)", 0.5 < pr["value"] < 0.95, str(pr["value"]))
chk("یک شاهد => اطمینان پایین", pr["confidence"] < 0.5, str(pr["confidence"]))
chk("evidence_count ثبت شد", pr["evidence_count"]==1)

# سوال تطبیقی نباید تکراری باشد
nx=c.get("/api/questionnaire/next").json()["question"]
chk("سوال تکراری ارائه نمی‌شود", nx["code"]!="q_start_delay")

# چند پاسخ همسو => اطمینان بالا می‌رود
for code,val in [("q_free_day","c"),("q_deadline","c"),("q_hard_first","d"),("q_routine","d")]:
    c.post("/api/onboarding/answers", json={"question_code":code,"answer_value":val})
p=c.get("/api/questionnaire/profile").json()
pr=[t for t in p["traits"] if t["key"]=="procrastination"][0]
chk("شواهد بیشتر => اطمینان بالاتر", pr["confidence"]>=0.5 and pr["reliable"], str(pr))
chk("مقدار به سمت بالا حرکت کرد", pr["value"]>0.7, str(pr["value"]))

h=c.get("/api/questionnaire/profile").json()["hints"]
chk("توصیه برنامه‌ریزی تولید شد", len(h)>0 and any(x["trait"]=="procrastination" for x in h), str(h)[:200])

# تغییر پاسخ
c.post("/api/onboarding/answers", json={"question_code":"q_start_delay","answer_value":"1"})
allq=c.get("/api/questionnaire/questions").json()["questions"]
a=[x for x in allq if x["code"]=="q_start_delay"][0]
chk("تغییر پاسخ اعمال شد", a["answer"]=="1", str(a["answer"]))
cnt=c.get("/api/questionnaire/profile").json()["answered_questions"]
chk("پاسخ تکراری دوبار شمرده نمی‌شود", cnt==5, str(cnt))

# گزینه نامعتبر
r=c.post("/api/onboarding/answers", json={"question_code":"q_start_delay","answer_value":"99"})
chk("گزینه نامعتبر رد می‌شود", r.status_code==400, str(r.status_code))
r=c.post("/api/onboarding/answers", json={"question_code":"ناموجود","answer_value":"a"})
chk("سوال ناموجود رد می‌شود", r.status_code==400, str(r.status_code))

# تکمیل کامل
for qq in c.get("/api/questionnaire/questions").json()["questions"]:
    if not qq["answer"]:
        c.post("/api/onboarding/answers", json={"question_code":qq["code"],"answer_value":qq["options"][0]["key"]})
chk("پس از تکمیل، سوال بعدی نداریم", c.get("/api/questionnaire/next").json()["question"] is None)

# reset
c.delete("/api/questionnaire")
chk("reset پاک کرد", c.get("/api/questionnaire/profile").json()["answered_questions"]==0)

print(f"\n>>> {ok} OK / {fail} FAIL")
sys.exit(1 if fail else 0)
