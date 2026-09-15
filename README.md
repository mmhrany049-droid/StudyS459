# SS459 — سیستم مدیریت و تحلیل مطالعه (نسخه ۱)

سیستم یکپارچه تک‌کاربره برای مدیریت و اندازه‌گیری فرایند یادگیری شخصی —
**نه** یک Todo App ساده.

**چرخه اصلی:** برنامه‌ریزی (جمعه) → اجرا → ثبت شواهد → تصحیح →
تحلیل → تشخیص وضعیت → مرور/جبران → برنامه‌ریزی مجدد

مستندات کامل نسخه ۱: [`study_system_v1_docs/`](study_system_v1_docs/)
(شروع از `00_MASTER_README.md` — کد مجوز: 459)

## Stack (سند ۱۲)

| بخش | تکنولوژی |
|---|---|
| Frontend | React + Vite + TypeScript + Tailwind (RTL/فارسی) |
| Backend | Python + FastAPI + Pydantic + SQLAlchemy |
| DB | SQLite (پیش‌فرض) — آماده PostgreSQL با `DATABASE_URL` |
| Integration | تلگرام فقط افزونه اختیاری (برنامه بدون آن کامل کار می‌کند) |

## راه‌اندازی سریع

### Backend (ترمینال ۱)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

- Health: <http://localhost:8000/health>
- مستندات API: <http://localhost:8000/docs>

### Frontend (ترمینال ۲)

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173
```

فرانت‌اند با URL نسبی کار می‌کند و Vite مسیرهای API را به بک‌اند
proxy می‌کند (بدون مشکل CORS). جزئیات: `frontend/README.md`.

### تست‌ها

```bash
cd backend && source .venv/bin/activate && pytest -q
cd frontend && npm run typecheck && npm run build
```

## ساختار

```
StudyS459/
  study_system_v1_docs/   # ۲۲ فایل مستندات نسخه ۱ (منبع حقیقت)
  backend/
    app/                  # main/config/logging/errors/db + api/v1/health
    alembic/              # مهاجرت‌ها (هر تغییر اسکیما = یک migration)
    tests/                # pytest
  frontend/
    src/                  # shell + routing + api client + صفحات پایه
```

مسیرهای URL دقیقاً مطابق `study_system_v1_docs/14_API_CONTRACT_V1.md`
سرو می‌شوند (بدون پیشوند `/api/v1` در URL).

قرارداد خطا (همه خطاها):

```json
{"error": {"code": "not_found", "message": "...", "details": null}}
```

## وضعیت Phaseها (سند ۱۵/۱۶)

- [x] **Phase 0** — Foundation (config/logging/migrations/health/error envelope)
- [x] **Phase 1** — Book Engine (config-driven، بدون hard-code)
- [x] **Phase 2** — Test Engine (با Range + زوج/فرد)
- [x] **Phase 3** — Analytics پایه (Coverage ≠ Accuracy ≠ Volume)
- [x] **Phase 4** — Goals (تعداد/موضوع، بدون double-count)
- [x] **Phase 5** — Planner (قانون جمعه + School Override)
- [x] **Phase 6** — Academic (مدرسه/کلاس/تکلیف/امتحان)
- [x] **Phase 7** — Student State + Reward (امتیاز/streak/نشان)
- [x] **Phase 8** — UI کامل + Hardening (تنظیمات، داشبورد کامل، گارد race، تست انطباق قرارداد)

گزارش هر Phase در PR/کامیت همان Phase ثبت می‌شود.
