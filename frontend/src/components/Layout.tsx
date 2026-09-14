import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/utils/cn";

const NAV = [
  { to: "/", label: "داشبورد", end: true },
  { to: "/today", label: "امروز" },
  { to: "/week", label: "هفته" },
  { to: "/test", label: "تست" },
  { to: "/progress", label: "پیشرفت" },
  { to: "/books", label: "کتاب‌ها" },
  { to: "/schedule", label: "برنامه مدرسه" },
  { to: "/homework", label: "تکالیف" },
  { to: "/exams", label: "امتحانات" },
  { to: "/rewards", label: "جوایز" },
  { to: "/settings", label: "تنظیمات" },
];

export default function Layout() {
  return (
    <div className="min-h-screen">
      <header className="bg-slate-900 text-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-3">
          <span className="ml-4 font-bold">SS459</span>
          <nav className="flex flex-wrap gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "rounded px-3 py-1 text-sm",
                    isActive ? "bg-white text-slate-900" : "hover:bg-slate-700",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
