import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Bar, Card, Chip, EmptyState, ErrorBox, InfoBox, Modal, SectionTitle, Spinner } from '../ui'
import { faNum, IRAN_WEEKDAYS, jalali, weekDays, weekStartOf } from '../jalali'
import { NewTaskModal } from './Today'

export default function Week() {
  const { me, toast, reloadMe } = useApp()
  const [week, setWeek] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showInterview, setShowInterview] = useState(false)
  const [showGoals, setShowGoals] = useState(false)
  const [showEval, setShowEval] = useState(false)
  const [showNew, setShowNew] = useState<string | null>(null)
  const [weekShift, setWeekShift] = useState(0)

  const weekStart = me
    ? new Date(new Date(me.today.week_start).getTime() + weekShift * 7 * 86400000).toISOString().slice(0, 10)
    : ''

  const load = () => {
    if (!weekStart) return
    setLoading(true)
    api.get(`/planner/week/${weekStart}`)
      .then(setWeek).catch((e) => setErr(errMessage(e))).finally(() => setLoading(false))
  }
  useEffect(load, [weekStart])

  if (!me || loading) return <Spinner />
  if (err) return <ErrorBox message={err} />

  const act = async (fn: () => Promise<any>, msg: string) => {
    try { const r = await fn(); toast(msg); load(); reloadMe(); return r } catch (e) { setErr(errMessage(e)) }
  }

  const gp = week.goal_progress

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-extrabold">برنامهٔ هفته</h2>
          <div className="text-xs text-slate-400 mt-1">{week.display} (شنبه تا جمعه)</div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button className="btn-ghost" onClick={() => setWeekShift((w) => w - 1)}>→ هفته قبل</button>
          <button className="btn-ghost" onClick={() => setWeekShift(0)}>این هفته</button>
          <button className="btn-ghost" onClick={() => setWeekShift((w) => w + 1)}>هفته بعد ←</button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button className="btn-primary" onClick={() => act(() => api.post('/planning/generate', { week_start: weekStart }),
          'برنامهٔ پیشنهادی هفته ساخته شد — پیشنهاد است، نه اجبار')}>
          ✨ ساخت برنامه هفته
        </button>
        <button className="btn-soft" onClick={() => setShowInterview(true)}>
          🗣️ مصاحبهٔ ابتدای هفته {!week.interview.available ? '' : week.interview.completed ? '✓' : '(نیمه‌کاره)'}
        </button>
        <button className="btn-soft" onClick={() => setShowGoals(true)}>🎯 هدف‌های هفته</button>
        <button className="btn-ghost" onClick={() => act(() => api.post('/planning/rebuild', { week_start: weekStart }),
          'برنامه بازسازی شد — کارهای دستی دست‌نخورده ماندند')}>
          🔄 بازسازی برنامه
        </button>
        <button className="btn-ghost" onClick={() => setShowEval(true)}>📊 ارزیابی هفته</button>
      </div>

      {gp?.midweek_warning && (
        <InfoBox color="amber">⚠️ {gp.midweek_warning.message} (پیشرفت فعلی: {faNum(Math.round((gp.midweek_warning.progress) * 100))}٪)</InfoBox>
      )}

      {/* تخته هفتگی */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        {week.days.map((d: any, i: number) => (
          <DayColumn key={d.date} d={d} idx={i} today={me.today.iso} act={act}
            onAdd={() => setShowNew(d.date)} />
        ))}
      </div>

      {gp && (gp.count_target || gp.topic_node) && (
        <Card>
          <SectionTitle>پیشرفت هدف‌های هفته</SectionTitle>
          <div className="grid sm:grid-cols-2 gap-4">
            {gp.count_target && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-500">هدف تعداد تست</span>
                  <span className="tabular-nums">{faNum(gp.attempted_week)} / {faNum(gp.count_target)}</span>
                </div>
                <Bar value={gp.count_progress ?? 0} color="bg-brand-500" />
              </div>
            )}
            {gp.topic_node && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-slate-500">هدف موضوعی: {gp.topic_node.title}</span>
                  <span className="tabular-nums">{pctOf(gp.topic_progress)}</span>
                </div>
                <Bar value={gp.topic_progress ?? 0} color="bg-violet-500" />
              </div>
            )}
          </div>
        </Card>
      )}

      <InterviewModal open={showInterview} onClose={() => setShowInterview(false)} weekStart={weekStart} onDone={load} />
      <GoalsModal open={showGoals} onClose={() => setShowGoals(false)} weekStart={weekStart} onDone={load} />
      <EvalModal open={showEval} onClose={() => setShowEval(false)} weekStart={weekStart} />
      {showNew && <NewTaskModal open={!!showNew} onClose={() => setShowNew(null)} date={showNew}
        onDone={() => { setShowNew(null); load() }} />}
    </div>
  )
}

function pctOf(x: number | null) {
  return x === null || x === undefined ? '—' : faNum(Math.round(x * 100)) + '٪'
}

function DayColumn({ d, idx, today, act, onAdd }: { d: any; idx: number; today: string; act: any; onAdd: () => void }) {
  const [dragOver, setDragOver] = useState(false)
  const isToday = d.date === today
  const isCatchup = idx >= 5

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const taskId = e.dataTransfer.getData('text/plain')
    if (taskId) act(() => api.post(`/tasks/${taskId}/move`, { date: d.date }), 'کار جابه‌جا شد')
  }

  return (
    <div onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)} onDrop={onDrop}
      className={`card p-3 min-h-44 transition ${dragOver ? 'ring-2 ring-brand-300 border-brand-200' : ''} ${isToday ? '!border-brand-300' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className={`text-sm font-bold ${isToday ? 'text-brand-700' : ''}`}>{IRAN_WEEKDAYS[idx]}</div>
          <div className="text-[10px] text-slate-400">{jalali(d.date)}</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {d.day_type === 'school'
            ? <Chip color="blue">مدرسه</Chip>
            : <Chip color={isCatchup ? 'amber' : 'green'}>{isCatchup ? 'جمعه‌بندی' : 'آزاد'}</Chip>}
          {d.classes.length > 0 && <Chip color="violet">{faNum(d.classes.length)} کلاس</Chip>}
        </div>
      </div>
      {d.tasks.length === 0 ? (
        <button className="w-full text-center text-xs text-slate-300 hover:text-brand-400 py-4 border border-dashed border-slate-100 rounded-xl"
          onClick={onAdd}>+ افزودن</button>
      ) : (
        <div className="space-y-1.5">
          {d.tasks.map((t: any) => (
            <WeekTask key={t.id} t={t} act={act} />
          ))}
        </div>
      )}
    </div>
  )
}

function WeekTask({ t, act }: { t: any; act: any }) {
  const done = t.status === 'completed'
  return (
    <div draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', String(t.id))}
      title="بکش و در روز دیگر رها کن"
      className={`rounded-lg border p-2 text-xs cursor-grab active:cursor-grabbing transition
        ${done ? 'border-emerald-100 bg-emerald-50/60 text-slate-400' : 'border-slate-100 bg-white hover:border-brand-200'}`}>
      <div className={`font-medium leading-snug ${done ? 'line-through' : ''}`}>
        {done && '✓ '}{t.title}
      </div>
      <div className="flex flex-wrap items-center gap-1 mt-1">
        {t.source === 'manual' && <Chip color="violet">دستی</Chip>}
        {t.source === 'planner' && <Chip color="blue">پیشنهاد</Chip>}
        {t.task_type === 'test' && <span className="text-slate-400">{faNum(t.question_count)} تست</span>}
      </div>
      <div className="flex gap-1 mt-1.5">
        {!done && (
          <button className="text-[10px] text-emerald-600 hover:underline"
            onClick={() => act(() => api.post(`/tasks/${t.id}/complete`), '✅ انجام شد')}>تکمیل</button>
        )}
        <button className="text-[10px] text-rose-400 hover:underline"
          onClick={() => act(() => api.del(`/tasks/${t.id}`), 'حذف شد')}>حذف</button>
      </div>
    </div>
  )
}

/* ------------------------- مصاحبهٔ ابتدای هفته (V2.1) ------------------------- */

function InterviewModal({ open, onClose, weekStart, onDone }: {
  open: boolean; onClose: () => void; weekStart: string; onDone: () => void
}) {
  const [iv, setIv] = useState<any>(null)
  const { toast } = useApp()

  useEffect(() => {
    if (open) api.post(`/planning/weekly-interview/start?week=${weekStart}`).then(setIv).catch(() => {})
  }, [open, weekStart])

  if (!iv) return null

  const answer = async (qid: string, value: any) => {
    const r = await api.post(`/planning/weekly-interview/${weekStart}/answer`, { question_id: qid, answer: value })
    setIv(r)
  }
  const finish = async () => {
    await api.post(`/planning/weekly-interview/${weekStart}/complete`)
    toast('مصاحبه کامل شد — پاسخ‌ها ورودی Planner هستند، برنامه را قفل نمی‌کنند')
    onDone(); onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title="مصاحبهٔ برنامه‌ریزی ابتدای هفته" wide>
      <div className="space-y-5">
        <InfoBox>قبل از ساخت برنامهٔ هفته، شرایط واقعی هفته‌ات را بگوی. پاسخ‌ها فقط ورودی Planner هستند و برنامه را قفل نمی‌کنند.</InfoBox>
        <ProgressLine value={iv.answered_count / iv.total_count} label={`${faNum(iv.answered_count)} از ${faNum(iv.total_count)}`} />
        {iv.groups.map((g: any) => (
          <div key={g.id}>
            <div className="text-sm font-bold mb-2 text-brand-700">{g.title}</div>
            <div className="space-y-3">
              {g.questions.map((q: any) => (
                <div key={q.id} className="rounded-xl border border-slate-100 p-3">
                  <div className="text-sm mb-2">{q.text}</div>
                  <QuestionInput q={q} onAnswer={(v) => answer(q.id, v)} />
                </div>
              ))}
            </div>
          </div>
        ))}
        <button className="btn-primary w-full" onClick={finish}>اتمام مصاحبه</button>
      </div>
    </Modal>
  )
}

function ProgressLine({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-400 mb-1"><span>پیشرفت مصاحبه</span><span>{label}</span></div>
      <Bar value={value} color="bg-violet-500" />
    </div>
  )
}

function QuestionInput({ q, onAnswer }: { q: any; onAnswer: (v: any) => void }) {
  const DAYS = IRAN_WEEKDAYS
  if (q.type === 'days') {
    const selected: string[] = Array.isArray(q.answer) ? q.answer : []
    const toggle = (d: string) => {
      const s = selected.includes(d) ? selected.filter((x) => x !== d) : [...selected, d]
      onAnswer(s)
    }
    return (
      <div className="flex flex-wrap gap-1.5">
        {DAYS.map((d) => (
          <button key={d} onClick={() => toggle(d)}
            className={`chip cursor-pointer ${selected.includes(d) ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
            {d}
          </button>
        ))}
      </div>
    )
  }
  if (q.type === 'scale') {
    const v = typeof q.answer === 'number' ? q.answer : 0
    return (
      <div className="flex gap-1.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => onAnswer(n)}
            className={`w-9 h-9 rounded-lg text-sm font-bold cursor-pointer transition
              ${v === n ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
            {faNum(n)}
          </button>
        ))}
      </div>
    )
  }
  if (q.type === 'choice' && q.options) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {q.options.map((o: string) => (
          <button key={o} onClick={() => onAnswer(o)}
            className={`chip cursor-pointer ${q.answer === o ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
            {o}
          </button>
        ))}
      </div>
    )
  }
  if (q.type === 'subject') {
    const [subjects, setSubjects] = useState<any[] | null>(null)
    useEffect(() => { api.get('/subjects').then(setSubjects).catch(() => {}) }, [])
    return (
      <div className="flex flex-wrap gap-1.5">
        {(subjects ?? []).map((s: any) => (
          <button key={s.id} onClick={() => onAnswer(s.name)}
            className={`chip cursor-pointer ${q.answer === s.name ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
            {s.name}
          </button>
        ))}
        <button onClick={() => onAnswer('فرقی ندارد')}
          className={`chip cursor-pointer ${q.answer === 'فرقی ندارد' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'}`}>فرقی ندارد</button>
      </div>
    )
  }
  if (q.type === 'hours') {
    return <input type="number" className="input !w-32" min={0} max={80} defaultValue={q.answer ?? ''}
      onBlur={(e) => onAnswer(+e.target.value)} placeholder="ساعت" />
  }
  // text / text_or_none
  return <input className="input" defaultValue={typeof q.answer === 'string' ? q.answer : ''}
    onBlur={(e) => e.target.value && onAnswer(e.target.value)} placeholder="اختیاری…" />
}

/* ------------------------------ هدف‌های هفته ------------------------------ */

function GoalsModal({ open, onClose, weekStart, onDone }: {
  open: boolean; onClose: () => void; weekStart: string; onDone: () => void
}) {
  const [goals, setGoals] = useState<any>(null)
  const [countTarget, setCountTarget] = useState(100)
  const [topicNode, setTopicNode] = useState<number | ''>('')
  const [topicTarget, setTopicTarget] = useState(30)
  const [nodes, setNodes] = useState<any[]>([])
  const [books, setBooks] = useState<any[]>([])
  const { toast } = useApp()

  useEffect(() => {
    if (!open) return
    api.get(`/goals/weeks/${weekStart}`).then((g) => {
      setGoals(g)
      const cnt = g.items.find((i: any) => i.goal_type === 'count')
      if (cnt) setCountTarget(cnt.target_value)
    }).catch(() => {})
    api.get('/books').then(setBooks).catch(() => {})
  }, [open, weekStart])

  useEffect(() => {
    if (books.length && nodes.length === 0) {
      // بارگذاری فهرست مباحث برای انتخاب هدف موضوعی
      Promise.all(books.map((b: any) => api.get(`/books/${b.id}/nodes`).then((t: any) => ({ b, t }))))
        .then((rs) => {
          const flat: any[] = []
          const walk = (items: any[], path: string, bookTitle: string) => items.forEach((n: any) => {
            const p = path ? `${path} › ${n.title}` : n.title
            if (['title', 'section', 'subsection'].includes(n.node_type)) {
              flat.push({ id: n.id, label: `${bookTitle} › ${p}` })
            }
            if (n.children) walk(n.children, p, bookTitle)
          })
          rs.forEach(({ b, t }: any) => t.forEach((ch: any) => walk([ch], '', b.title)))
          setNodes(flat)
        }).catch(() => {})
    }
  }, [books])

  const save = async () => {
    const items: any[] = [{ goal_type: 'count', target_value: countTarget }]
    if (topicNode !== '') items.push({ goal_type: 'topic', target_value: topicTarget, node_id: topicNode })
    try {
      await api.post(`/goals/weeks/${weekStart}`, { items })
      toast('هدف‌های هفته ذخیره شد')
      onDone(); onClose()
    } catch (e) { toast(errMessage(e)) }
  }

  return (
    <Modal open={open} onClose={onClose} title="هدف‌های هفته">
      <div className="space-y-4">
        <InfoBox>دو نوع هدف مستقل‌اند: <b>تعداد</b> (حجم کلی) و <b>موضوعی</b> (اولویت دارد). می‌توانی یکی یا هر دو را تعیین کنی.</InfoBox>
        <div>
          <span className="text-xs font-medium text-slate-500 mb-1 block">هدف تعداد تست در هفته</span>
          <input type="number" className="input" value={countTarget} min={10} step={10}
            onChange={(e) => setCountTarget(+e.target.value)} />
        </div>
        <div>
          <span className="text-xs font-medium text-slate-500 mb-1 block">هدف موضوعی (اختیاری)</span>
          <select className="input" value={topicNode} onChange={(e) => setTopicNode(e.target.value ? +e.target.value : '')}>
            <option value="">— بدون هدف موضوعی —</option>
            {nodes.map((n: any) => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </div>
        {topicNode !== '' && (
          <div>
            <span className="text-xs font-medium text-slate-500 mb-1 block">تعداد تست روی این موضوع</span>
            <input type="number" className="input" value={topicTarget} min={5}
              onChange={(e) => setTopicTarget(+e.target.value)} />
          </div>
        )}
        <button className="btn-primary w-full" onClick={save}>ذخیره</button>
      </div>
    </Modal>
  )
}

/* ------------------------------ ارزیابی هفته ------------------------------ */

function EvalModal({ open, onClose, weekStart }: { open: boolean; onClose: () => void; weekStart: string }) {
  const [res, setRes] = useState<any>(null)
  const { toast } = useApp()

  const run = async () => {
    try {
      const r = await api.post(`/planning/evaluate?week=${weekStart}`)
      setRes(r)
      toast('حلقهٔ تطبیق اجرا شد — ظرفیت به‌روزرسانی شد')
    } catch (e) { toast(errMessage(e)) }
  }

  return (
    <Modal open={open} onClose={onClose} title="ارزیابی هفته — حلقهٔ یادگیری" wide>
      <div className="space-y-4">
        <InfoBox color="violet">
          Plan → Act → Observe → Evaluate → Update — سیستم از نتیجهٔ برنامه یاد می‌گیرد، نه اینکه تو را سرزنش کند.
        </InfoBox>
        {!res ? (
          <button className="btn-primary w-full" onClick={run}>اجرای ارزیابی</button>
        ) : (
          <div className="space-y-3">
            {res.updates.map((u: any, i: number) => <InfoBox key={i} color="blue">{u.message} (میانگین تکمیل: {faNum(Math.round(u.avg_completion_rate * 100))}٪)</InfoBox>)}
            <div className="rounded-xl border border-slate-100 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs">
                  <tr><th className="p-2 text-right">روز</th><th className="p-2">برنامه</th><th className="p-2">تکمیل</th><th className="p-2">نرخ</th></tr>
                </thead>
                <tbody>
                  {res.days.map((d: any) => (
                    <tr key={d.date} className="border-t border-slate-50">
                      <td className="p-2">{jalali(d.date)}</td>
                      <td className="p-2 text-center tabular-nums">{faNum(d.planned)}</td>
                      <td className="p-2 text-center tabular-nums">{faNum(d.completed)}</td>
                      <td className="p-2 text-center">
                        <Chip color={d.completion_rate >= 0.7 ? 'green' : d.completion_rate >= 0.4 ? 'amber' : 'red'}>
                          {faNum(Math.round(d.completion_rate * 100))}٪
                        </Chip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {res.days.length === 0 && <EmptyState icon="🍃" title="برای این هفته برنامه‌ای ثبت نشده بود" />}
          </div>
        )}
      </div>
    </Modal>
  )
}
