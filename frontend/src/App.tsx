import { NavLink, Route, Routes } from "react-router-dom";
import { Toaster } from "./components/ui";
import Dashboard from "./pages/Dashboard";
import Today from "./pages/Today";
import Books from "./pages/Books";
import QuestionBank from "./pages/QuestionBank";
import PastImport from "./pages/PastImport";
import Taught from "./pages/Taught";
import Exams from "./pages/Exams";
import ExamDetailPage from "./pages/ExamDetail";
import Readiness from "./pages/Readiness";
import TestRunner from "./pages/TestRunner";
import Progress from "./pages/Progress";
import Schedule from "./pages/Schedule";
import ProfilePage from "./pages/Profile";

const NAV = [
  { to: "/", label: "داشبورد", icon: "🏠", end: true },
  { to: "/today", label: "امروز و هفته", icon: "📆" },
  { to: "/books", label: "کتاب‌ها و بانک تست", icon: "📚" },
  { to: "/import", label: "ورود تست‌های قبلی", icon: "⬆️" },
  { to: "/taught", label: "تدریس‌شده", icon: "🎓" },
  { to: "/exams", label: "امتحانات", icon: "📝" },
  { to: "/readiness", label: "آمادگی امتحان", icon: "🎯" },
  { to: "/progress", label: "پیشرفت", icon: "📊" },
  { to: "/schedule", label: "کلاس‌ها", icon: "🗓️" },
  { to: "/profile", label: "پروفایل و پرسش‌نامه", icon: "🧭" },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <Toaster />
      <div className="mx-auto flex max-w-[1500px] gap-6 p-4 lg:p-6">
        <aside className="sticky top-6 hidden h-[calc(100vh-3rem)] w-64 shrink-0 flex-col rounded-2xl border border-surface-line bg-white p-4 shadow-card lg:flex">
          <div className="mb-6 px-2 pt-2">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-lg font-black text-white">
                S
              </div>
              <div>
                <div className="text-base font-black leading-tight">SS459</div>
                <div className="text-[11px] text-ink-mute">نسخه ۲.۲</div>
              </div>
            </div>
          </div>
          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-150 ${
                    isActive
                      ? "bg-brand-50 font-semibold text-brand-700"
                      : "text-ink-soft hover:bg-surface-alt hover:text-ink"
                  }`
                }
              >
                <span className="text-base">{n.icon}</span>
                <span>{n.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="mt-4 rounded-xl bg-surface-alt p-3 text-[11px] leading-5 text-ink-mute">
            بانک تست متصل به مبحث + تدریس‌شده + امتحان واقعی/آزمایشی + آمادگی امتحان
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <div className="mb-4 flex gap-1.5 overflow-x-auto rounded-2xl border border-surface-line bg-white p-2 shadow-card lg:hidden">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-xs ${
                    isActive ? "bg-brand-50 font-semibold text-brand-700" : "text-ink-soft"
                  }`
                }
              >
                <span>{n.icon}</span>
                <span>{n.label}</span>
              </NavLink>
            ))}
          </div>

          <main className="pb-10">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/today" element={<Today />} />
              <Route path="/books" element={<Books />} />
              <Route path="/books/:bookId/nodes/:nodeId/bank" element={<QuestionBank />} />
              <Route path="/import" element={<PastImport />} />
              <Route path="/taught" element={<Taught />} />
              <Route path="/exams" element={<Exams />} />
              <Route path="/exams/:examId" element={<ExamDetailPage />} />
              <Route path="/readiness" element={<Readiness />} />
              <Route path="/test/:sessionId" element={<TestRunner />} />
              <Route path="/progress" element={<Progress />} />
              <Route path="/schedule" element={<Schedule />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Routes>
          </main>
        </div>
      </div>
    </div>
  );
}
