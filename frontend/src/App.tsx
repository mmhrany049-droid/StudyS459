import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from './api'
import { faNum, jalali, weekdayFa } from './jalali'
import Dashboard from './pages/Dashboard'
import Today from './pages/Today'
import Week from './pages/Week'
import Tests from './pages/Tests'
import Review from './pages/Review'
import ImportPage from './pages/Import'
import Progress from './pages/Progress'
import Books from './pages/Books'
import Classes from './pages/Classes'
import Onboarding from './pages/Onboarding'
import Rewards from './pages/Rewards'
import Settings from './pages/Settings'

export type Me = {
  id: number; username: string; display_name: string; grade: string; track: string
  coins: number; total_points: number; current_streak: number; longest_streak: number
  settings: Record<string, any>
  today: { iso: string; jalali: string; weekday: string; week_start: string; season_mode: string }
}

type Ctx = { me: Me | null; reloadMe: () => void; go: (page: string, params?: any) => void; toast: (msg: string) => void }
const AppCtx = createContext<Ctx>(null as any)
export const useApp = () => useContext(AppCtx)

const NAV = [
  { id: 'dashboard', label: 'داشبورد', icon: '🏠' },
  { id: 'today', label: 'امروز', icon: '☀️' },
  { id: 'week', label: 'هفته', icon: '🗓️' },
  { id: 'tests', label: 'تست زدن', icon: '📝' },
  { id: 'review', label: 'مرور', icon: '🔁' },
  { id: 'import', label: 'وارد کردن تست قبلی', icon: '📥' },
  { id: 'progress', label: 'پیشرفت', icon: '📊' },
  { id: 'books', label: 'کتاب‌ها', icon: '📚' },
  { id: 'classes', label: 'کلاس‌ها', icon: '🏫' },
  { id: 'rewards', label: 'جوایز', icon: '🏆' },
  { id: 'questionnaire', label: 'پرسشنامه شناخت', icon: '🧭' },
  { id: 'settings', label: 'تنظیمات', icon: '⚙️' },
]

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [page, setPage] = useState('dashboard')
  const [params, setParams] = useState<any>(null)
  const [toasts, setToasts] = useState<{ id: number; msg: string }[]>([])
  const [navOpen, setNavOpen] = useState(false)

  const reloadMe = useCallback(() => {
    api.get<Me>('/auth/me').then(setMe).catch(() => {})
  }, [])

  useEffect(() => { reloadMe() }, [reloadMe])

  const go = useCallback((p: string, ps?: any) => {
    setPage(p); setParams(ps ?? null); setNavOpen(false)
    window.scrollTo({ top: 0 })
  }, [])

  const toast = useCallback((msg: string) => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, msg }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3400)
  }, [])

  const ctx: Ctx = { me, reloadMe, go, toast }

  const PAGES: Record<string, React.ReactNode> = {
    dashboard: <Dashboard />,
    today: <Today />,
    week: <Week />,
    tests: <Tests params={params} />,
    review: <Review />,
    import: <ImportPage />,
    progress: <Progress />,
    books: <Books />,
    classes: <Classes />,
    questionnaire: <Onboarding />,
    rewards: <Rewards />,
    settings: <Settings params={params} />,
  }

  return (
    <AppCtx.Provider value={ctx}>
      <div className="min-h-screen flex">
        {/* سایدبار */}
        <aside className={`fixed lg:sticky top-0 right-0 z-40 h-screen w-64 shrink-0 bg-white border-l border-slate-100
          flex flex-col transition-transform duration-200 ${navOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'}`}>
          <div className="p-5 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-white
                flex items-center justify-center font-extrabold text-lg shadow-md">۴۵۹</div>
              <div>
                <div className="font-extrabold leading-tight">سیستم مطالعه</div>
                <div className="text-[11px] text-slate-400">نسخه ۲٫۱ — SS459</div>
              </div>
            </div>
          </div>
          <nav className="flex-1 overflow-y-auto px-3 pb-4 space-y-0.5">
            {NAV.map((n) => (
              <button key={n.id}
                onClick={() => go(n.id)}
                className={`w-full flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium transition
                  ${page === n.id ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50'}`}>
                <span className="text-base">{n.icon}</span>{n.label}
              </button>
            ))}
          </nav>
          <div className="p-4 border-t border-slate-100 text-[11px] text-slate-400 leading-relaxed">
            هفته ایرانی: شنبه تا جمعه<br />تقویم هجری شمسی — Asia/Tehran
          </div>
        </aside>
        {navOpen && <div className="fixed inset-0 bg-slate-900/30 z-30 lg:hidden" onClick={() => setNavOpen(false)} />}

        {/* محتوا */}
        <div className="flex-1 min-w-0 flex flex-col">
          <header className="sticky top-0 z-20 bg-white/80 backdrop-blur border-b border-slate-100">
            <div className="flex items-center gap-3 px-4 md:px-6 h-14">
              <button className="btn-ghost !px-2.5 lg:hidden" onClick={() => setNavOpen(true)} aria-label="منو">☰</button>
              <div className="min-w-0">
                {me && (
                  <div className="text-sm font-bold truncate">
                    {weekdayFa(me.today.iso)} <span className="text-slate-400 font-normal">·</span> {jalali(me.today.iso)}
                  </div>
                )}
              </div>
              <div className="flex-1" />
              {me && (
                <>
                  <div className="chip bg-amber-50 text-amber-700" title="سکه مطالعه">
                    🪙 {faNum(me.coins)}
                  </div>
                  <div className="chip bg-orange-50 text-orange-600" title="Streak روزهای پیاپی">
                    🔥 {faNum(me.current_streak)}
                  </div>
                </>
              )}
            </div>
          </header>
          <main className="flex-1 p-4 md:p-6 max-w-6xl w-full mx-auto" key={page}>
            <div className="anim-page">{PAGES[page] ?? null}</div>
          </main>
          <footer className="px-6 py-4 text-center text-[11px] text-slate-400">
            SS459 — برنامه پیشنهاد می‌دهد، تو تصمیم می‌گیری. · اطلاعات مستندات نسخه ۲ و ۲٫۱
          </footer>
        </div>

        {/* توست */}
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] space-y-2 w-max max-w-[92vw]">
          {toasts.map((t) => (
            <div key={t.id} className="anim-pop card !py-2.5 !px-4 text-sm font-medium text-slate-700 shadow-lg flex items-center gap-2">
              <span>✨</span>{t.msg}
            </div>
          ))}
        </div>
      </div>
    </AppCtx.Provider>
  )
}
