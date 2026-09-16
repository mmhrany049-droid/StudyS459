"""
تطبیق قرارداد API با سند 09_API_V2_2.md
اجرا:  cd backend && ../.venv/bin/python tests/test_api_contract_v2_2.py
"""
import sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config as cfg
base = Path(__file__).resolve().parent / "_tmp_contract"
shutil.rmtree(base, ignore_errors=True); base.mkdir(parents=True)
cfg.DATA_DIR = base
cfg.STORAGE_DIR = base/"storage"; cfg.STORAGE_DIR.mkdir()
cfg.DB_PATH = base/"t.db"
cfg.DATABASE_URL = f"sqlite:///{cfg.DB_PATH}"
import app.db as dbm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
dbm.engine = create_engine(f"sqlite:///{cfg.DB_PATH}", connect_args={"check_same_thread": False})
dbm.SessionLocal = sessionmaker(bind=dbm.engine, autoflush=False, autocommit=False)
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
c.__enter__()

ok=fail=0
def chk(name, cond, extra=""):
    global ok, fail
    if cond: ok+=1; print("  OK  ", name)
    else: fail+=1; print("  FAIL", name, extra)

nodes = c.get("/api/books/1/nodes?with_stats=false").json()["nodes"]
def leaves(l):
    for n in l:
        if not n["children"]: yield n
        else: yield from leaves(n["children"])
L = list(leaves(nodes))
n1, n2 = L[0]["id"], L[1]["id"]

# --- doc 09 official nested paths
r = c.post(f"/api/books/1/nodes/{n1}/questions/range", json={"from":1,"to":10})
chk("سند۰۹ POST /books/{id}/nodes/{nid}/questions/range", r.status_code==200 and r.json()["created"]==10, r.text[:200])

r = c.put(f"/api/books/1/nodes/{n1}/questions/bulk", json={"compact":"1,2,3,4,1,2,3,4,1,2"})
chk("سند۰۹ PUT /books/{id}/nodes/{nid}/questions/bulk", r.status_code==200 and r.json()["updated"]==10, r.text[:200])

r = c.get(f"/api/books/1/nodes/{n1}/questions")
chk("سند۰۹ GET /books/{id}/nodes/{nid}/questions", r.status_code==200 and len(r.json()["questions"])==10, r.text[:200])

# short aliases still work
r = c.get(f"/api/nodes/{n1}/questions")
chk("نام مستعار کوتاه /nodes/{nid}/questions", r.status_code==200 and len(r.json()["questions"])==10)

# --- doc 09 sequence_ref import
c.post(f"/api/nodes/{n2}/questions/range", json={"from":1,"to":5})
c.put(f"/api/nodes/{n2}/questions/bulk", json={"compact":"4,4,4,4,4"})

# sequence_ref + node_id  (شماره ۱..۵ در دو مبحث تکراری است → node_id لازم)
body={"book_id":1,"answers":[
  {"sequence_ref":1,"node_id":n2,"choice":4},
  {"sequence_ref":2,"node_id":n2,"choice":1},
  {"sequence_ref":3,"node_id":n2,"choice":None},
]}
r=c.post("/api/attempts/import-by-book", json=body)
j=r.json()
chk("سند۰۹ import با sequence_ref+node_id",
    r.status_code==200 and j["correct"]==1 and j["wrong"]==1 and j["unanswered"]==1, r.text[:300])
chk("import سکه نمی‌دهد", j.get("coins_awarded",0)==0, str(j))

# sequence_ref یکتا در کل کتاب (شماره ۹ فقط در n1 هست چون n2 تا ۵ است)
r=c.post("/api/attempts/import-by-book", json={"book_id":1,"answers":[{"sequence_ref":9,"choice":1}]})
chk("سند۰۹ import با sequence_ref بدون node_id (یکتا)",
    r.status_code==200 and r.json()["imported"]==1, r.text[:300])

# مبهم: شماره ۱ در دو مبحث → باید نادیده گرفته شود نه خطا/اشتباه
r=c.post("/api/attempts/import-by-book", json={"book_id":1,"answers":[{"sequence_ref":1,"choice":1}]})
chk("sequence_ref مبهم نادیده گرفته می‌شود", r.status_code==400 or r.json().get("imported",0)==0, r.text[:200])

# question_id قدیمی هنوز کار می‌کند
qs=c.get(f"/api/nodes/{n1}/questions").json()["questions"]
r=c.post("/api/attempts/import-by-book", json={"book_id":1,"answers":[{"question_id":qs[4]["id"],"choice":1}]})
chk("import با question_id (سازگاری قبلی)", r.status_code==200 and r.json()["imported"]==1, r.text[:200])

print(f"\n>>> {ok} OK / {fail} FAIL")
sys.exit(1 if fail else 0)
