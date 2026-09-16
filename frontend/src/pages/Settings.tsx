import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Bar, Card, Chip, EmptyState, InfoBox, SectionTitle, Spinner, StatTile, Toggle } from '../ui'
import { faNum, jalali } from '../jalali'
import { PersonalityView } from './Onboarding'

/** تنظیمات — تنظیمات V2 + ثبت وضعیت + رفتار (V2.1) */

export default function Settings({ params }: { params?: any }) {
  const { me, reloadMe, toast } = useApp()
  const [tab, setTab] = useState(params?.tab ?? 'general')
  const [autoTime, setAutoTime] = useState(true)
  const [season, setSeason] = useState('')
  const [behavior, setBehavior] = useState<any>(null)
  const [checkin, setCheckin] = useState({ energy: 3, focus: 3, motivation: 3, stress: 3, fatigue: 3, sleep_hours: 7 })

  useEffect(() => {
    if (!me) return
    setAutoTime(me.settings?.auto_time_adjust ?? true)
    setSeason(me.settings?.season_override ?? '')
  }, [me])

  useEffect(() => {
    if (tab === 'behavior') api.get('/behavior/summary').then(setBehavior).catch(() => {})
  }, [tab])

  if (!me) return <Spinner />

  const saveSettings = async () => {
    try {
      await api.patch('/settings', { auto_time_adjust: autoTime, season_override: season || 'none' })
      toast('تنظیمات ذخیره شد')
      reloadMe()
    } catch (e) { toast(errMessage(e)) }
  }

  const submitCheckin = async () => {
    try {
      const r = await api.post('/state/check-in', checkin)
      toast(`${r.message} (آمادگی: ${faNum(Math.round(r.readiness * 100))}٪)`)
    } catch (e) { toast(errMessage(e)) }
  }

  const TABS = [
    { id: 'general', label: 'عمومی' },
    { id: 'state', label: 'ثبت وضعیت امروز' },
    { id: 'behavior', label: 'رفتار و اهمال‌کاری' },
    { id: 'model', label: 'مدل کاربر' },
  ]

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex gap-1.5 flex-wrap">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`btn ${tab === t.id ? 'bg-brand-600 text-white' : 'btn-ghost'} !py-2 text-xs`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <Card>
          <SectionTitle>تنظیمات</SectionTitle>
          <div className="space-y-1">
            <Toggle checked={autoTime} onChange={setAutoTime}
              label="تطبیق خودکار زمان در تست Timed (اگر دقت ≥۷۵٪ و حداقل ۲۰ تلاش، محدودیت ×۰٫۸ تا کف ۶۰ ثانیه)" />
          </div>
          <div className="mt-4">
            <span className="text-xs font-medium text-slate-500 mb-1 block">حالت فصل</span>
            <select className="input" value={season} onChange={(e) => setSeason(e.target.value)}>
              <option value="">خودکار (بر اساس تقویم شمسی)</option>
              <option value="school_term">حالت مدرسه (پاییز/زمستان/بهار)</option>
              <option value="summer">حالت تعطیلات (تابستان — ظرفیت کامل)</option>
            </select>
            <div className="text-[11px] text-slate-400 mt-1">
              حالت فعلی: {me.today.season_mode === 'summer' ? 'تعطیلات' : 'مدرسه'} · امروز: {jalali(me.today.iso)}
            </div>
          </div>
          <button className="btn-primary mt-4" onClick={saveSettings}>ذخیره</button>
        </Card>
      )}

      {tab === 'state' && (
        <Card>
          <SectionTitle>وضعیت الان چطور است؟</SectionTitle>
          <InfoBox>
            این یک State لحظه‌ای است — با شخصیت تو فرق دارد. فقط پیشنهادهای امروز را تعدیل می‌کند و
            مستقلاً Task نمی‌سازد.
          </InfoBox>
          <div className="space-y-4 mt-4">
            {([['energy', 'انرژی'], ['focus', 'تمرکز'], ['motivation', 'انگیزه'],
              ['stress', 'استرس'], ['fatigue', 'خستگی']] as const).map(([k, label]) => (
              <div key={k}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500 font-medium">{label}</span>
                  <span className="text-slate-400 tabular-nums">{faNum(checkin[k])} / ۵</span>
                </div>
                <input type="range" min={1} max={5} value={checkin[k]} className="w-full accent-brand-600"
                  onChange={(e) => setCheckin({ ...checkin, [k]: +e.target.value })} />
              </div>
            ))}
            <div>
              <span className="text-xs font-medium text-slate-500 mb-1 block">خواب دیشب (ساعت)</span>
              <input type="number" step={0.5} min={0} max={14} className="input !w-32"
                value={checkin.sleep_hours} onChange={(e) => setCheckin({ ...checkin, sleep_hours: +e.target.value })} />
            </div>
            <button className="btn-primary w-full" onClick={submitCheckin}>ثبت وضعیت</button>
          </div>
        </Card>
      )}

      {tab === 'behavior' && (
        <>
          <Card>
            <SectionTitle>ویژگی‌های رفتاری (مشاهده‌شده)</SectionTitle>
            {!behavior ? <Spinner /> : (
              <>
                <InfoBox color="violet">
                  این اعداد از رفتار واقعی تو محاسبه می‌شوند، نه از پاسخ‌های پرسشنامه — و هر زمان قابل بازمحاسبه‌اند.
                </InfoBox>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
                  <StatTile icon="✅" label="نرخ تکمیل کار" value={faNum(Math.round(behavior.features.task_completion_rate * 100)) + '٪'} />
                  <StatTile icon="⏱️" label="میانگین جلسه" value={behavior.features.average_session_minutes ? faNum(Math.round(behavior.features.average_session_minutes)) + ' دقیقه' : '—'} />
                  <StatTile icon="🌅" label="تمرکز صبح" value={faNum(Math.round(behavior.features.avg_focus_morning * 100)) + '٪'} color="text-amber-600" />
                  <StatTile icon="🌙" label="تمرکز عصر/شب" value={faNum(Math.round(behavior.features.avg_focus_evening * 100)) + '٪'} color="text-violet-600" />
                  <StatTile icon="🐌" label="شروع دیرهنگام" value={faNum(Math.round(behavior.features.late_start_rate * 100)) + '٪'} color="text-rose-500" />
                  <StatTile icon="🧗" label="رد کار سخت" value={faNum(Math.round(behavior.features.hard_task_skip_rate * 100)) + '٪'} color="text-rose-500" />
                </div>
              </>
            )}
          </Card>

          {behavior?.procrastination && (
            <Card>
              <SectionTitle extra={<Chip color={behavior.procrastination.pattern_detected ? 'red' : 'green'}>
                {behavior.procrastination.pattern_detected ? 'الگو شناسایی شد' : 'الگوی واضح نیست'}
              </Chip>}>
                تحلیل الگوی اهمال‌کاری
              </SectionTitle>
              <InfoBox color={behavior.procrastination.pattern_detected ? 'amber' : 'green'}>
                {behavior.procrastination.message}
                {behavior.procrastination.pattern_detected &&
                  ` (قدرت سیگنال: ${faNum(Math.round(behavior.procrastination.signal_strength * 100))}٪ · اطمینان: ${faNum(Math.round(behavior.procrastination.confidence * 100))}٪)`}
              </InfoBox>
              {behavior.procrastination.pattern_detected && (
                <div className="space-y-1.5 mt-3">
                  {behavior.procrastination.suggestions.map((s: string) => (
                    <div key={s} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
                      <span>💡</span>{s}
                    </div>
                  ))}
                </div>
              )}
              <div className="text-[11px] text-slate-400 mt-3">
                این یک مشاهدهٔ رفتاری برای برنامه‌ریزی است — نه قضاوت یا تشخیص.
              </div>
            </Card>
          )}

          {behavior?.recent_events?.length > 0 && (
            <Card>
              <SectionTitle>رویدادهای رفتاری اخیر (append-only)</SectionTitle>
              <div className="max-h-64 overflow-y-auto space-y-1 text-xs">
                {behavior.recent_events.map((e: any) => (
                  <div key={e.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5">
                    <span className="text-slate-600 font-medium">{e.type}</span>
                    <span className="text-slate-400">{e.source === 'self_report' ? 'خودگزارشی' : 'مشاهده‌شده'}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      {tab === 'model' && (
        <UserModelTab />
      )}
    </div>
  )
}

function UserModelTab() {
  const [model, setModel] = useState<any>(null)
  useEffect(() => { api.get('/user-model').then(setModel).catch(() => {}) }, [])
  if (!model) return <Spinner />
  return (
    <div className="space-y-4">
      <PersonalityView model={model} />
      <Card>
        <SectionTitle>رفتار مشاهده‌شده (جدا از self-report)</SectionTitle>
        {Object.keys(model.behavior ?? {}).length === 0 ? (
          <EmptyState icon="🔭" title="هنوز دادهٔ رفتاری کافی نیست" hint="با استفاده از سیستم جمع می‌شود" />
        ) : (
          <div className="space-y-3">
            {Object.entries(model.behavior).map(([k, v]: any) => (
              <div key={k}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600 font-medium">{featureLabel(k)}</span>
                  <span className="text-slate-400 tabular-nums">{faNum(Math.round(v.value * 100))}٪</span>
                </div>
                <Bar value={v.value} color="bg-brand-400" />
              </div>
            ))}
          </div>
        )}
      </Card>
      <Card>
        <SectionTitle>ترجیحات</SectionTitle>
        {Object.keys(model.preferences ?? {}).length === 0 ? (
          <EmptyState icon="🎛️" title="ترجیحی ثبت نشده" hint="از پرسشنامه یا مصاحبهٔ هفتگی جمع می‌شود" />
        ) : (
          <div className="space-y-1.5">
            {Object.entries(model.preferences).map(([k, v]: any) => (
              <div key={k} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span>{prefLabel(k)}</span>
                <span className="text-slate-500">{String(v.value ?? v)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function featureLabel(k: string): string {
  const m: Record<string, string> = {
    task_completion_rate: 'نرخ تکمیل کار', avg_focus_morning: 'تمرکز صبح',
    avg_focus_evening: 'تمرکز عصر/شب', average_session_minutes: 'میانگین مدت جلسه (نرمال)',
    late_start_rate: 'نرخ شروع دیرهنگام', hard_task_skip_rate: 'نرخ رد کردن کار سخت',
  }
  return m[k] ?? k
}

function prefLabel(k: string): string {
  const m: Record<string, string> = {
    preferred_study_time: 'بازهٔ مطالعهٔ ترجیحی', plan_style: 'سبک برنامه', task_size: 'اندازهٔ کارها',
  }
  return m[k] ?? k
}
