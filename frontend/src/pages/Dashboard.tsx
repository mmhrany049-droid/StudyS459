import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Bar, Card, Chip, EmptyState, ErrorBox, InfoBox, SectionTitle, StatTile } from '../ui'
import { faNum, jalali, pct } from '../jalali'

export default function Dashboard() {
  const { me, go, toast, reloadMe } = useApp()
  const [overview, setOverview] = useState<any>(null)
  const [rewards, setRewards] = useState<any>(null)
  const [dayPlan, setDayPlan] = useState<any>(null)
  const [review, setReview] = useState<any>(null)
  const [habits, setHabits] = useState<any>(null)
  const [state, setState] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => {
    if (!me) return
    api.get('/progress/overview').then(setOverview).catch(() => {})
    api.get('/rewards/summary').then(setRewards).catch(() => {})
    api.get(`/planner/day/${me.today.iso}`).then(setDayPlan).catch(() => {})
    api.get('/review/summary').then(setReview).catch(() => {})
    api.get('/habits/summary').then(setHabits).catch(() => {})
    api.get('/state/current').then(setState).catch(() => {})
  }
  useEffect(load, [me?.today.iso])

  if (!me) return null

  const wakeUp = async () => {
    setBusy(true)
    try {
      const r = await api.post('/rewards/wake-up')
      toast(r.message)
      reloadMe(); load()
    } catch (e) { setErr(errMessage(e)) } finally { setBusy(false) }
  }

  const todayTasks = dayPlan?.tasks ?? []
  const done = todayTasks.filter((t: any) => t.status === 'completed').length
  const goalProg = dayPlan?.capacity_recommendation

  return (
    <div className="space-y-5">
      {err && <ErrorBox message={err} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile icon="🪙" label="سکه مطالعه" value={faNum(me.coins)} sub={`مجموع امتیاز: ${faNum(me.total_points)}`} color="text-amber-600" />
        <StatTile icon="🔥" label="Streak فعلی" value={faNum(me.current_streak)} sub={`رکورد: ${faNum(me.longest_streak)}`} color="text-orange-500" />
        <StatTile icon="🎯" label="دقت کل" value={pct(overview?.accuracy)} sub={`حجم: ${faNum(overview?.volume ?? 0)} تلاش`} color="text-emerald-600" />
        <StatTile icon="🗺️" label="پوشش" value={pct(overview?.coverage)} sub={`از ${faNum(overview?.total ?? 0)} سوال`} color="text-brand-600" />
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {/* وضعیت امروز */}
        <Card className="md:col-span-2">
          <SectionTitle extra={<Chip color={me.today.season_mode === 'summer' ? 'amber' : 'blue'}>
            {me.today.season_mode === 'summer' ? 'حالت تعطیلات' : 'حالت مدرسه'}
          </Chip>}>
            امروز — {jalali(me.today.iso)}
          </SectionTitle>

          {!rewards?.wake_up_today && (
            <div className="rounded-xl bg-gradient-to-l from-amber-50 to-orange-50 border border-amber-100 p-4 mb-4
              flex items-center justify-between gap-3 flex-wrap">
              <div className="text-sm text-amber-800">
                <b>بیدار شدی؟</b> ثبت تا ساعت ۰۷:۰۰ → +۱۵ سکه (قبل ۰۶:۴۵ → +۵ اضافی)
              </div>
              <button className="btn-primary !bg-amber-500 hover:!bg-amber-600" disabled={busy} onClick={wakeUp}>
                ☀️ بیدار شدم
              </button>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-slate-50 p-3">
              <div className="text-2xl font-extrabold text-brand-600 tabular-nums">{faNum(done)}<span className="text-slate-300">/</span>{faNum(todayTasks.length)}</div>
              <div className="text-xs text-slate-400 mt-1">کارهای امروز</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-3">
              <div className="text-2xl font-extrabold text-rose-500 tabular-nums">{faNum(review?.due ?? 0)}</div>
              <div className="text-xs text-slate-400 mt-1">آماده مرور</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-3">
              <div className="text-2xl font-extrabold text-emerald-600 tabular-nums">{faNum(overview?.correct ?? 0)}</div>
              <div className="text-xs text-slate-400 mt-1">پاسخ درست تاکنون</div>
            </div>
          </div>

          {goalProg && (
            <div className="mt-4">
              <div className="text-xs text-slate-400 mb-1">توصیه امروز: {faNum(goalProg.recommended_tasks)} کار
                {goalProg.conservative ? ' (محافظه‌کارانه — هنوز ۳۰ روز داده نداری)' : ''}</div>
              <Bar value={todayTasks.length ? done / todayTasks.length : 0} color="bg-emerald-500" />
            </div>
          )}

          <div className="flex gap-2 mt-4 flex-wrap">
            <button className="btn-primary" onClick={() => go('today')}>برنامه امروز</button>
            <button className="btn-soft" onClick={() => go('tests')}>شروع تست</button>
            <button className="btn-soft" onClick={() => go('review')}>مرور غلط‌ها</button>
          </div>
        </Card>

        {/* وضعیت لحظه‌ای V2.1 */}
        <Card>
          <SectionTitle>وضعیت الان</SectionTitle>
          {state ? (
            <div className="space-y-2.5">
              {(['energy', 'focus', 'motivation', 'stress', 'fatigue', 'readiness'] as const).map((k) => {
                const labels: Record<string, string> = { energy: 'انرژی', focus: 'تمرکز', motivation: 'انگیزه', stress: 'استرس', fatigue: 'خستگی', readiness: 'آمادگی' }
                const v = state.state[k] ?? 0
                const conf = state.confidence?.[k] ?? 0
                const good = k === 'stress' || k === 'fatigue' ? 1 - v : v
                return (
                  <div key={k}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-500">{labels[k]}</span>
                      <span className="text-slate-400 tabular-nums">{faNum(Math.round(v * 100))}٪
                        <span className="text-slate-300"> · اطمینان {faNum(Math.round(conf * 100))}٪</span></span>
                    </div>
                    <Bar value={good} color={good > 0.6 ? 'bg-emerald-500' : good > 0.35 ? 'bg-amber-400' : 'bg-rose-400'} />
                  </div>
                )
              })}
              <button className="btn-ghost w-full mt-1" onClick={() => go('settings', { tab: 'state' })}>
                ثبت وضعیت امروز
              </button>
              <div className="text-[10px] text-slate-400 leading-relaxed">
                وضعیت لحظه‌ای با شخصیت تو یکی نیست و فقط پیشنهادها را تغذیه می‌کند.
              </div>
            </div>
          ) : <EmptyState icon="🫧" title="هنوز وضعیتی ثبت نشده" hint="از تنظیمات → ثبت وضعیت" />}
        </Card>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {/* پیشنهادهای امروز */}
        <Card>
          <SectionTitle extra={<button className="btn-ghost !py-1.5 !px-3 text-xs" onClick={() => go('today')}>جزئیات</button>}>
            پیشنهاد سیستم برای امروز
          </SectionTitle>
          {(dayPlan?.suggestions ?? []).length === 0 ? (
            <EmptyState icon="🌱" title="پیشنهادی در صف نیست" hint="هدف هفتگی تعیین کن یا برنامه هفته را بساز" />
          ) : (
            <div className="space-y-2">
              {(dayPlan?.suggestions ?? []).slice(0, 4).map((s: any) => (
                <div key={s.test_set_id} className="rounded-xl border border-slate-100 p-3 hover:border-brand-200 transition">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-medium text-sm truncate">{s.title}</div>
                    <Chip color="blue">{faNum(s.score)} امتیاز</Chip>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">{s.reasons.join(' + ')}</div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* یادگیری عادت (فقط بعد از ۳۰ روز) */}
        <Card>
          <SectionTitle>یادگیری عادت</SectionTitle>
          {habits ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">روزهای فعال</span>
                <span className="font-bold tabular-nums">{faNum(habits.active_days)} / {faNum(habits.threshold_days)}</span>
              </div>
              <Bar value={habits.active_days / habits.threshold_days} color="bg-violet-500" />
              {habits.past_threshold && habits.advice ? (
                <InfoBox color="violet">{habits.advice.message}</InfoBox>
              ) : (
                <InfoBox>
                  بعد از {faNum(30)} روز داده، سیستم نظر واقعی‌ات را دربارهٔ «تعداد کار روزانه» می‌گوید — نه قبل از آن.
                </InfoBox>
              )}
            </div>
          ) : <EmptyState icon="📈" title="داده عادت هنوز جمع نشده" />}
        </Card>
      </div>

      {/* نشان‌های اخیر */}
      {rewards?.badges?.length > 0 && (
        <Card>
          <SectionTitle extra={<button className="btn-ghost !py-1.5 !px-3 text-xs" onClick={() => go('rewards')}>همه</button>}>
            نشان‌های اخیر
          </SectionTitle>
          <div className="flex flex-wrap gap-2">
            {rewards.badges.slice(0, 8).map((b: any) => (
              <div key={b.code} className="chip bg-amber-50 text-amber-700 !px-3 !py-1.5" title={b.description}>
                🏅 {b.title}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
