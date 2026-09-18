import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./lib/api";
import { toPersianDigits } from "./lib/format";
import Calendar from "./pages/Calendar";
import Dashboard from "./pages/Dashboard";
import Curriculum from "./pages/Curriculum";
import QuestionBank from "./pages/QuestionBank";
import ResponseSheet from "./pages/ResponseSheet";
import ImportPast from "./pages/ImportPast";
import Planner from "./pages/Planner";
import Today from "./pages/Today";
import Exams from "./pages/Exams";
import Goals from "./pages/Goals";
import Review from "./pages/Review";
import Progress from "./pages/Progress";
import Lab from "./pages/Lab";
import Settings from "./pages/Settings";
import { Spinner } from "./components/ui";

const NAV = [
  { to: "/", label: "امروز", icon: "◉" },
  { to: "/calendar", label: "تقویم", icon: "▩" },
  { to: "/plan", label: "برنامه هفته", icon: "▦" },
  { to: "/curriculum", label: "مباحث و کتاب‌ها", icon: "▤" },
  { to: "/bank", label: "بانک تست", icon: "▥" },
  { to: "/sheet", label: "پاسخ‌برگ", icon: "▧" },
  { to: "/import", label: "ورود تلاش گذشته", icon: "↧" },
  { to: "/review", label: "مرور", icon: "↻" },
  { to: "/exams", label: "امتحان‌ها", icon: "★" },
  { to: "/goals", label: "هدف‌ها", icon: "◎" },
  { to: "/progress", label: "تحلیل", icon: "◔" },
  { to: "/lab", label: "آزمایشگاه", icon: "⚗" },
  { to: "/settings", label: "تنظیمات", icon: "⚙" },
];

type Bootstrap = {
  model_version?: string;
  date_long?: string;
  week_label?: string;
  user?: { display_name?: string };
  onboarding?: { done?: boolean; next_question?: unknown };
  books?: unknown[];
};

export default function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    api
      .post<Bootstrap>("/bootstrap")
      .then(setBoot)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-xl p-8" dir="rtl">
        <div className="card">
          <h1 className="mb-2 text-lg font-semibold">اتصال به سرور برقرار نشد</h1>
          <p className="muted">{error}</p>
          <p className="muted mt-2">
            مطمئن شو بک‌اند در حال اجراست (<code dir="ltr">uvicorn app.main:app</code>) و پروکسی{" "}
            <code dir="ltr">/api</code> فعال است.
          </p>
        </div>
      </div>
    );
  }

  if (!boot) return <Spinner label="در حال آماده‌سازی…" />;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-ink-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 text-lg text-white">س</span>
            <div>
              <div className="text-sm font-semibold leading-4">سیستم مطالعه</div>
              <div className="text-[11px] text-ink-600">
                {boot.date_long} — هفته {boot.week_label}
              </div>
            </div>
          </div>
          <nav className="order-3 flex w-full gap-1 overflow-x-auto rounded-2xl bg-ink-100 p-1 lg:order-2 lg:w-auto lg:flex-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `tab ${isActive && location.pathname === item.to ? "tab-active" : ""}`}
              >
                <span className="ml-1 text-xs">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="order-2 flex items-center gap-2 lg:order-3">
            <span className="badge-muted">
              نسخه {toPersianDigits(boot.model_version?.replace(/^v/, "") ?? "3.1.0")}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/calendar" element={<Calendar />} />
          <Route path="/plan" element={<Planner />} />
          <Route path="/curriculum" element={<Curriculum />} />
          <Route path="/bank" element={<QuestionBank />} />
          <Route path="/sheet" element={<ResponseSheet />} />
          <Route path="/import" element={<ImportPast />} />
          <Route path="/review" element={<Review />} />
          <Route path="/exams" element={<Exams />} />
          <Route path="/goals" element={<Goals />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/lab" element={<Lab />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <footer className="mx-auto max-w-7xl px-4 pb-10 text-center text-[11px] text-ink-400">
        داده خام ≠ داده مشتق — هر عدد مشتق قابل بازسازی است و هر تصمیم دلیل قابل مشاهده دارد.
      </footer>
    </div>
  );
}
