import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Card, Chip, EmptyState, ErrorBox, InfoBox, Modal, SectionTitle, Spinner } from '../ui'
import { faNum, jalali } from '../jalali'

const STATUS_LABEL: Record<string, string> = {
  planned: 'برنامه‌ریزی‌شده', in_progress: 'در حال انجام', completed: 'انجام‌شده', cancelled: 'لغو‌شده',
}
const SOURCE_LABEL: Record<string, string> = {
  manual: 'دستی', planner: 'پیشنهاد سیستم', imported: 'واردشده', recurring: 'تکرارشونده',
}

export default function Today() {
  const { me, toast, reloadMe } = useApp()
  const [day, setDay] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showNew, setShowNew] = useState(false)
  const [dateOffset, setDateOffset] = useState(0)

  const date = me ? new Date(new Date(me.today.iso).getTime() + dateOffset * 86400000).toISOString().slice(0, 10) : ''

  const load = () => {
    if (!date) return
    setLoading(true)
    api.get(`/planner/day/${date}`)
      .then(setDay).catch((e) => setErr(errMessage(e))).finally(() => setLoading(false))
  }
  useEffect(load, [date])

  if (!me || loading) return <Spinner />
  if (err) return <ErrorBox message={err} />

  const act = async (fn: () => Promise<any>, msg: string) => {
    try { await fn(); toast(msg); load(); reloadMe() } catch (e) { setErr(errMessage(e)) }
  }

  const tasks = day.tasks
  const est = day.tasks.reduce((s: number, t: any) => s + (t.estimated_minutes ?? 60), 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-extrabold">
            {dateOffset === 0 ? 'امروز' : dateOffset > 0 ? 'فرداها' : 'روزهای قبل'} — {jalali(date)}
          </h2>
          <div className="text-xs text-slate-400 mt-1">
            {day.day_info.weekday} · {day.day_info.day_type === 'school' ? 'روز مدرسه' : 'روز آزاد / جمعه‌بندی'} ·
            {' '}ظرفیت {faNum(day.day_info.capacity_minutes)} دقیقه
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-ghost" onClick={() => setDateOffset((d) => d - 1)}>→ روز قبل</button>
          <button className="btn-ghost" onClick={() => setDateOffset(0)}>امروز</button>
          <button className="btn-ghost" onClick={() => setDateOffset((d) => d + 1)}>روز بعد ←</button>
          <button className="btn-primary" onClick={() => setShowNew(true)}>+ کار دستی</button>
        </div>
      </div>

      {day.over_capacity && (
        <InfoBox color="amber">
          ⚠️ {day.over_capacity_warning} ({faNum(est)} دقیقه)
          {day.low_priority_suggestions.map((t: any) => ` «${t.title}»`).join('،')}
        </InfoBox>
      )}

      {day.day_info.overridden && (
        <InfoBox color="green">این روز با override علامت خورده (مدرسه نمی‌روم) — ظرفیت ×۱٫۳۵</InfoBox>
      )}

      {day.capacity_recommendation && (
        <InfoBox>
          💡 ظرفیت تخمینی: <b>{faNum(day.capacity_recommendation.recommended_tasks)} کار</b>
          {' '}(پایه: {faNum(day.capacity_recommendation.estimated_capacity)}، اطمینان {faNum(Math.round(day.capacity_recommendation.confidence * 100))}٪
          {day.capacity_recommendation.conservative ? ' — محافظه‌کارانه' : ''})
        </InfoBox>
      )}

      <Card>
        <SectionTitle extra={<Chip color="blue">{faNum(tasks.filter((t: any) => t.status === 'completed').length)} / {faNum(tasks.length)}</Chip>}>
          کارهای این روز
        </SectionTitle>
        {tasks.length === 0 ? (
          <EmptyState icon="🌤️" title="برای این روز کاری ثبت نشده"
            hint="از «هفته» برنامه بساز یا کار دستی اضافه کن" />
        ) : (
          <div className="space-y-2">
            {tasks.map((t: any) => <TaskRow key={t.id} t={t} act={act} />)}
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle>پیشنهادهای سیستم (با دلیل)</SectionTitle>
        {day.suggestions.length === 0 ? (
          <EmptyState icon="🌱" title="پیشنهادی نیست" hint="برای دریافت پیشنهاد، هدف هفتگی تعیین کن" />
        ) : (
          <div className="space-y-2">
            {day.suggestions.map((s: any) => (
              <div key={s.test_set_id} className="rounded-xl border border-slate-100 p-3 flex items-center justify-between gap-3 hover:border-brand-200 transition">
                <div className="min-w-0">
                  <div className="font-medium text-sm truncate">{s.title}</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {s.reasons.join(' + ')} · parity پیشنهادی: {s.parity === 'odd' ? 'فرد' : 'زوج'}
                  </div>
                </div>
                <button className="btn-soft shrink-0"
                  onClick={() => act(() => api.post('/tasks', {
                    title: `${s.subject ?? ''} — ${s.title}`.trim(), task_type: 'test', date,
                    book_id: s.book_id, node_id: s.node_id, question_count: 15, parity: s.parity,
                  }), 'به برنامهٔ امروز اضافه شد')}>افزودن</button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <NewTaskModal open={showNew} onClose={() => setShowNew(false)} date={date}
        onDone={() => { setShowNew(false); load() }} />
    </div>
  )
}

function TaskRow({ t, act }: { t: any; act: (fn: () => Promise<any>, msg: string) => void }) {
  const [open, setOpen] = useState(false)
  const { go } = useApp()
  const done = t.status === 'completed'
  return (
    <div className={`rounded-xl border p-3 transition ${done ? 'border-emerald-100 bg-emerald-50/50' : 'border-slate-100 hover:border-brand-200'}`}>
      <div className="flex items-start gap-3">
        <button className={`mt-0.5 w-6 h-6 rounded-lg border-2 flex items-center justify-center shrink-0 transition
          ${done ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-300 hover:border-brand-400'}`}
          aria-label={done ? 'برگشت به برنامه' : 'تکمیل'}
          onClick={() => act(() => api.post(`/tasks/${t.id}/${done ? 'uncomplete' : 'complete'}`),
            done ? 'به برنامه برگشت' : '✅ انجام شد — سکه و streak به‌روز شد')}>
          {done && <span className="text-xs">✓</span>}
        </button>
        <div className="flex-1 min-w-0">
          <div className={`font-medium text-sm ${done ? 'line-through text-slate-400' : ''}`}>{t.title}</div>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            <Chip color={t.source === 'manual' ? 'violet' : 'blue'}>{SOURCE_LABEL[t.source] ?? t.source}</Chip>
            {t.task_type === 'test' && <Chip>{faNum(t.question_count)} تست · {t.parity === 'odd' ? 'فرد' : t.parity === 'even' ? 'زوج' : 'همه'}</Chip>}
            {t.estimated_minutes && <Chip>{faNum(t.estimated_minutes)} دقیقه</Chip>}
            <Chip color="slate">اولویت {faNum(t.priority)}</Chip>
            {t.manual_override && <Chip color="violet">دست‌نخورده توسط Planner</Chip>}
          </div>
          {t.recommendation_reason && !done && (
            <div className="text-[11px] text-slate-400 mt-1.5">💡 {t.recommendation_reason}</div>
          )}
        </div>
        <div className="flex flex-col gap-1 shrink-0">
          {t.task_type === 'test' && !done && (
            <button className="btn-ghost !py-1.5 !px-3 text-xs"
              onClick={() => go('tests', { task: t })}>شروع</button>
          )}
          <button className="btn-ghost !py-1.5 !px-3 text-xs" onClick={() => setOpen(!open)}>…</button>
        </div>
      </div>
      {open && (
        <TaskActions t={t} act={act} />
      )}
    </div>
  )
}

function TaskActions({ t, act }: { t: any; act: (fn: () => Promise<any>, msg: string) => void }) {
  const [date, setDate] = useState(t.date)
  return (
    <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2 text-xs">
      <label className="flex items-center gap-1.5">
        <span className="text-slate-400">جابه‌جایی به</span>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input !py-1 !px-2 !w-auto text-xs" />
      </label>
      <button className="btn-soft !py-1.5"
        onClick={() => act(() => api.post(`/tasks/${t.id}/move`, { date }), 'جابه‌جا شد')}>انتقال</button>
      <button className="btn-soft !py-1.5"
        onClick={() => act(() => api.post(`/tasks/${t.id}/split`, { ratio: 0.5 }), 'کار به دو نیمه split شد')}>Split</button>
      <button className="btn-danger !py-1.5"
        onClick={() => act(() => api.del(`/tasks/${t.id}`), 'حذف شد')}>حذف</button>
      {t.source === 'planner' && (
        <button className="btn-danger !py-1.5"
          onClick={() => act(() => api.post(`/tasks/${t.id}/reject-suggestion`), 'پیشنهاد رد شد — به‌عنوان evidence ثبت شد')}>رد پیشنهاد</button>
      )}
    </div>
  )
}

export function NewTaskModal({ open, onClose, date, onDone }: {
  open: boolean; onClose: () => void; date: string; onDone: () => void
}) {
  const [title, setTitle] = useState('')
  const [type, setType] = useState('study')
  const [minutes, setMinutes] = useState(60)
  const { toast } = useApp()

  const save = async () => {
    if (!title.trim()) return
    try {
      await api.post('/tasks', { title: title.trim(), task_type: type, date, estimated_minutes: minutes })
      toast('کار دستی اضافه شد — Planner آن را تغییر نمی‌دهد')
      onDone()
    } catch (e) { toast(errMessage(e)) }
  }

  return (
    <Modal open={open} onClose={onClose} title="کار دستی جدید">
      <div className="space-y-3">
        <div>
          <span className="text-xs font-medium text-slate-500 mb-1 block">عنوان</span>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="مثلاً: مرور جزوهٔ فیزیک — فصل کار و انرژی" autoFocus />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <span className="text-xs font-medium text-slate-500 mb-1 block">نوع</span>
            <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="study">مطالعه (غیرتست)</option>
              <option value="test">تست</option>
            </select>
          </div>
          <div>
            <span className="text-xs font-medium text-slate-500 mb-1 block">مدت تخمینی (دقیقه)</span>
            <input type="number" className="input" value={minutes} min={10} max={300}
              onChange={(e) => setMinutes(+e.target.value)} />
          </div>
        </div>
        <InfoBox>کارهای دستی با برچسب «دستی» ذخیره می‌شوند و Planner هرگز بدون اجازهٔ تو آن‌ها را overwrite نمی‌کند.</InfoBox>
        <button className="btn-primary w-full" onClick={save}>افزودن</button>
      </div>
    </Modal>
  )
}
