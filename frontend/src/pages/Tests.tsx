import React, { useEffect, useMemo, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Bar, Card, Chip, EmptyState, ErrorBox, InfoBox, Modal, SectionTitle, Spinner } from '../ui'
import { faNum, pct } from '../jalali'

/** صفحهٔ تست — انتخاب مبحث/بازه/parity → اجرا → نتیجه (سند 06 و 11) */

export default function Tests({ params }: { params?: any }) {
  const { me, toast, reloadMe, go } = useApp()
  const [books, setBooks] = useState<any[]>([])
  const [nodes, setNodes] = useState<any[] | null>(null)
  const [testSets, setTestSets] = useState<any[]>([])
  const [sel, setSel] = useState<{ book?: any; node?: any; testSet?: any }>({})
  const [form, setForm] = useState({ count: 10, parity: 'any', from: '' as string | number, to: '' as string | number, timed: false, timeLimit: 600 })
  const [session, setSession] = useState<any>(null)
  const [result, setResult] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [durationModal, setDurationModal] = useState<number | null>(null)
  const [parityState, setParityState] = useState<any>(null)
  const [task] = useState<any>(params?.task ?? null)

  useEffect(() => { api.get('/books').then(setBooks).catch(() => {}) }, [])

  // اگر از «امروز» با Task آمده‌ایم
  useEffect(() => {
    if (!task || books.length === 0) return
    const b = books.find((x: any) => x.id === task.book_id)
    if (b) {
      setSel((s) => ({ ...s, book: b }))
      api.get(`/books/${b.id}/nodes`).then((tree: any) => {
        const find = (items: any[]): any => {
          for (const n of items) {
            if (n.id === task.node_id) return n
            const f = find(n.children ?? [])
            if (f) return f
          }
          return null
        }
        const node = find(tree)
        if (node) selectNode(node, b)
      }).catch(() => {})
    }
  }, [task, books])

  const selectBook = (b: any) => {
    setSel({ book: b })
    setTestSets([]); setParityState(null)
    api.get(`/books/${b.id}/nodes`).then(setNodes).catch(() => {})
  }

  const selectNode = async (node: any, book?: any) => {
    setSel({ book: book ?? sel.book, node })
    setTestSets([])
    try {
      const ps = await api.get(`/nodes/${node.id}/parity-state`)
      setParityState(ps)
      if (ps.suggested_next && ps.suggested_next !== 'any') setForm((f) => ({ ...f, parity: ps.suggested_next }))
      const sets = await api.get(`/nodes/${node.id}/test-sets`)
      setTestSets(sets)
      const first = sets.find((s: any) => s.test_type === 'normal') ?? sets[0]
      if (first) setSel((s) => ({ ...s, testSet: first }))
    } catch (e) { setErr(errMessage(e)) }
  }

  const start = async () => {
    if (!sel.testSet) return
    setBusy(true); setErr(null)
    try {
      const body: any = {
        test_set_id: sel.testSet.id, count: form.count, parity: form.parity, timed: form.timed,
        sequence_from: form.from === '' ? null : +form.from,
        sequence_to: form.to === '' ? null : +form.to,
      }
      if (form.timed) body.time_limit_seconds = form.timeLimit
      if (task) body.task_id = task.id
      const s = await api.post('/test-sessions', body)
      setSession(s)
    } catch (e) {
      setErr(errMessage(e))
    } finally { setBusy(false) }
  }

  if (session) {
    return <SessionRunner session={session} onDone={(res) => {
      setSession(null); setResult(res); reloadMe()
      if (res.needs_duration_input) setDurationModal(res.id)
    }} />
  }
  if (result) {
    return <ResultView result={result} onBack={() => { setResult(null); loadFresh() }} />
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {err && <ErrorBox message={err} />}
      {task && <InfoBox>در حال شروع تست از کار «{task.title}»</InfoBox>}

      <Card>
        <SectionTitle>شروع جلسهٔ تست</SectionTitle>
        <div className="space-y-4">
          {/* کتاب */}
          <div>
            <span className="text-xs font-medium text-slate-500 mb-1.5 block">کتاب</span>
            <div className="flex flex-wrap gap-2">
              {books.map((b) => (
                <button key={b.id} onClick={() => selectBook(b)}
                  className={`btn ${sel.book?.id === b.id ? 'bg-brand-600 text-white' : 'btn-ghost'}`}>
                  {b.title} <span className="text-[10px] opacity-60">{b.publisher}</span>
                </button>
              ))}
            </div>
          </div>

          {/* درخت مبحث */}
          {nodes && (
            <div>
              <span className="text-xs font-medium text-slate-500 mb-1.5 block">مبحث</span>
              <NodeTree nodes={nodes} selected={sel.node} onSelect={(n) => selectNode(n)} />
            </div>
          )}

          {/* test set */}
          {testSets.length > 0 && (
            <div>
              <span className="text-xs font-medium text-slate-500 mb-1.5 block">مجموعهٔ تست</span>
              <div className="flex flex-wrap gap-2">
                {testSets.map((ts) => (
                  <button key={ts.id}
                    onClick={() => setSel((s) => ({ ...s, testSet: ts }))}
                    className={`btn ${sel.testSet?.id === ts.id ? 'bg-brand-600 text-white' : 'btn-ghost'}`}>
                    {ts.title} <span className="text-[10px] opacity-60">({faNum(ts.question_count)})</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {parityState && parityState.last_parity && (
            <InfoBox color="violet">
              آخرین parity این مبحث: <b>{parityState.last_parity === 'odd' ? 'فرد' : 'زوج'}</b> — پیشنهاد سیستم برای این بار: <b>{parityState.suggested_next === 'odd' ? 'فرد' : 'زوج'}</b>
            </InfoBox>
          )}

          {/* تنظیمات جلسه */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <label className="block">
              <span className="text-xs font-medium text-slate-500 mb-1 block">تعداد سوال</span>
              <input type="number" className="input" min={1} max={60} value={form.count}
                onChange={(e) => setForm({ ...form, count: +e.target.value })} />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500 mb-1 block">Parity</span>
              <select className="input" value={form.parity} onChange={(e) => setForm({ ...form, parity: e.target.value })}>
                <option value="any">همه</option>
                <option value="odd">فقط فرد</option>
                <option value="even">فقط زوج</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500 mb-1 block">از سوال شماره</span>
              <input type="number" className="input" min={1} placeholder="ابتدا" value={form.from}
                onChange={(e) => setForm({ ...form, from: e.target.value })} />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-500 mb-1 block">تا سوال شماره</span>
              <input type="number" className="input" min={1} placeholder="انتها" value={form.to}
                onChange={(e) => setForm({ ...form, to: e.target.value })} />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" className="accent-brand-600 w-4 h-4" checked={form.timed}
                onChange={(e) => setForm({ ...form, timed: e.target.checked })} />
              زمان‌دار (Timed)
            </label>
            {form.timed && (
              <label className="flex items-center gap-2 text-sm">
                محدودیت (ثانیه):
                <input type="number" className="input !w-24 !py-1.5" value={form.timeLimit} min={60} step={30}
                  onChange={(e) => setForm({ ...form, timeLimit: +e.target.value })} />
              </label>
            )}
            <button className="btn-primary mr-auto" disabled={!sel.testSet || busy} onClick={start}>
              {busy ? '…' : '🚀 شروع جلسه'}
            </button>
          </div>
        </div>
      </Card>

      <DurationModal sessionId={durationModal} onClose={() => setDurationModal(null)} />
    </div>
  )

  function loadFresh() { /* حالت شروع مجدد */ }
}

/* --------------------------- درخت انتخاب مبحث --------------------------- */

export function NodeTree({ nodes, selected, onSelect, depth = 0 }: { nodes: any[]; selected?: any; onSelect: (n: any) => void; depth?: number }) {
  const [open, setOpen] = useState<Record<number, boolean>>({})
  return (
    <div className="rounded-xl border border-slate-100 p-2 max-h-64 overflow-y-auto bg-slate-50/50">
      {nodes.map((n) => (
        <div key={n.id} style={{ paddingRight: depth * 14 }}>
          <div className={`flex items-center gap-1.5 py-1 px-2 rounded-lg text-sm
            ${selected?.id === n.id ? 'bg-brand-600 text-white' : 'hover:bg-white cursor-pointer'}`}>
            {n.children?.length > 0 ? (
              <button className="w-5 h-5 shrink-0 flex items-center justify-center text-slate-400 hover:text-brand-500"
                onClick={() => setOpen((o) => ({ ...o, [n.id]: !o[n.id] }))}
                aria-label="باز/بسته">{open[n.id] ? '▾' : '◂'}</button>
            ) : <span className="w-5" />}
            <button className="flex-1 text-right truncate" onClick={() => onSelect(n)}>{n.title}</button>
            {n.last_parity && <span className={`text-[9px] ${selected?.id === n.id ? 'text-white/70' : 'text-slate-400'}`}>
              {n.last_parity === 'odd' ? 'فرد' : 'زوج'}
            </span>}
          </div>
          {open[n.id] && n.children?.length > 0 && (
            <NodeTree nodes={n.children} selected={selected} onSelect={onSelect} depth={depth + 1} />
          )}
        </div>
      ))}
    </div>
  )
}

/* ------------------------------ اجرای جلسه ------------------------------ */

function SessionRunner({ session, onDone }: { session: any; onDone: (res: any) => void }) {
  const { toast } = useApp()
  const [idx, setIdx] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [chosen, setChosen] = useState<Record<number, number>>({})
  const [finished, setFinished] = useState(false)
  const [remaining, setRemaining] = useState(session.time_limit_seconds ?? 0)
  const q = session.questions[idx]
  const answeredCount = Object.keys(answers).length

  useEffect(() => {
    if (!session.timed || finished) return
    const t = setInterval(() => {
      setRemaining((r: number) => {
        if (r <= 1) {
          clearInterval(t)
          finish(true)
          return 0
        }
        return r - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [session.timed, finished])

  const mark = async (result: string, answer?: string) => {
    if (answers[q.id]) return
    setAnswers((a) => ({ ...a, [q.id]: result }))
    if (answer) setChosen((c) => ({ ...c, [q.id]: +answer }))
    try {
      await api.post(`/test-sessions/${session.id}/answers`, { question_id: q.id, result, answer })
    } catch (e) {
      toast(errMessage(e))
    }
    if (idx < session.questions.length - 1) {
      setTimeout(() => setIdx((i) => i + 1), 160)
    }
  }

  const finish = async (timeout: boolean = false) => {
    if (finished) return
    setFinished(true)
    try {
      const res = await api.post(`/test-sessions/${session.id}/finish`)
      if (timeout) toast('⏰ زمان تمام شد — سوالات بی‌پاسخ «نزده» ثبت شدند')
      onDone(res)
    } catch (e) { toast(errMessage(e)) }
  }

  const mm = Math.floor(remaining / 60), ss = remaining % 60

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="text-sm text-slate-500">
          سوال {faNum(idx + 1)} از {faNum(session.questions.length)}
          <span className="text-slate-300"> · </span>
          {faNum(answeredCount)} پاسخ‌داده
          {session.parity !== 'any' && <Chip color="blue">{session.parity === 'odd' ? 'فرد' : 'زوج'}</Chip>}
        </div>
        {session.timed && (
          <div className={`chip tabular-nums ${remaining < 60 ? 'bg-rose-50 text-rose-600' : 'bg-slate-100 text-slate-600'}`}>
            ⏱ {faNum(String(mm).padStart(2, '0'))}:{faNum(String(ss).padStart(2, '0'))}
          </div>
        )}
      </div>

      <Bar value={(idx + 1) / session.questions.length} />

      <Card className="text-center py-10">
        <div className="text-slate-400 text-sm mb-1">سوال شمارهٔ {faNum(q.sequence_no)}</div>
        <div className="text-3xl font-extrabold text-slate-700 mb-6">{faNum(q.sequence_no)}</div>
        <div className="text-xs text-slate-400 mb-6">پاسخ خود را با کلید گزینه ثبت کن</div>
        <div className="flex justify-center gap-2 sm:gap-3 flex-wrap">
          {[1, 2, 3, 4].map((n) => (
            <button key={n} disabled={!!answers[q.id]}
              onClick={() => mark(String(n) === q.answer_key ? 'correct' : 'wrong', String(n))}
              className={`w-16 h-16 rounded-2xl text-2xl font-extrabold transition active:scale-95
                ${answers[q.id]
                  ? (String(n) === q.answer_key
                      ? 'bg-emerald-500 text-white shadow-md'
                      : chosen[q.id] === n
                        ? 'bg-rose-500 text-white'
                        : 'bg-slate-50 text-slate-300')
                  : 'bg-brand-50 text-brand-700 hover:bg-brand-100 border border-brand-100 cursor-pointer'}`}>
              {faNum(n)}
            </button>
          ))}
        </div>
        {answers[q.id] && (
          <div className="mt-6 anim-pop">
            <Chip color={answers[q.id] === 'correct' ? 'green' : 'red'}>
              {answers[q.id] === 'correct' ? '✓ درست — +۲ سکه' : answers[q.id] === 'wrong' ? '✗ غلط — وارد صف مرور' : 'نزده'}
            </Chip>
          </div>
        )}
      </Card>

      <div className="flex items-center justify-between gap-2">
        <button className="btn-ghost" disabled={idx === 0} onClick={() => setIdx((i) => i - 1)}>→ قبلی</button>
        <div className="flex gap-1.5 flex-wrap justify-center">
          {session.questions.map((qq: any, i: number) => (
            <button key={qq.id} onClick={() => setIdx(i)}
              className={`w-7 h-7 rounded-lg text-[11px] font-bold transition
                ${i === idx ? 'bg-brand-600 text-white'
                  : answers[qq.id] === 'correct' ? 'bg-emerald-100 text-emerald-600'
                  : answers[qq.id] === 'wrong' ? 'bg-rose-100 text-rose-500'
                  : answers[qq.id] === 'unanswered' ? 'bg-amber-100 text-amber-600'
                  : 'bg-slate-100 text-slate-400 hover:bg-slate-200'}`}
              aria-label={`سوال ${i + 1}`}>
              {faNum(i + 1)}
            </button>
          ))}
        </div>
        {idx < session.questions.length - 1
          ? <button className="btn-ghost" onClick={() => setIdx((i) => i + 1)}>بعدی ←</button>
          : <button className="btn-primary" onClick={() => finish()}>پایان جلسه ✓</button>}
      </div>

      <div className="text-center">
        <button className="btn-ghost text-xs" onClick={() => mark('unanswered')}>نزده — رد کردن این سوال</button>
      </div>
    </div>
  )
}

/* -------------------------------- نتیجه -------------------------------- */

function ResultView({ result, onBack }: { result: any; onBack: () => void }) {
  return (
    <div className="max-w-3xl space-y-4">
      <Card>
        <div className="text-center py-4">
          <div className="anim-pop text-5xl mb-3">
            {result.accuracy >= 0.8 ? '🎉' : result.accuracy >= 0.5 ? '👌' : '💪'}
          </div>
          <div className="text-3xl font-extrabold">{pct(result.accuracy)}</div>
          <div className="text-xs text-slate-400 mt-1">دقت (در پاسخ‌های داده‌شده)</div>
          <div className="flex justify-center gap-6 mt-5 text-center">
            <div><div className="text-2xl font-extrabold text-emerald-600 tabular-nums">{faNum(result.correct)}</div><div className="text-xs text-slate-400">درست (+۲ سکه هرکدام)</div></div>
            <div><div className="text-2xl font-extrabold text-rose-500 tabular-nums">{faNum(result.wrong)}</div><div className="text-xs text-slate-400">غلط → صف مرور</div></div>
            <div><div className="text-2xl font-extrabold text-amber-500 tabular-nums">{faNum(result.unanswered)}</div><div className="text-xs text-slate-400">نزده</div></div>
            <div><div className="text-2xl font-extrabold text-slate-600 tabular-nums">{faNum(result.total)}</div><div className="text-xs text-slate-400">کل</div></div>
          </div>
          <div className="text-xs text-slate-400 mt-4">
            parity: {result.parity === 'odd' ? 'فرد' : result.parity === 'even' ? 'زوج' : 'همه'}
            {result.range?.[0] ? ` · بازهٔ ${faNum(result.range[0])} تا ${faNum(result.range[1])}` : ''}
            {result.rewards?.coins ? ` · 🪙 +${faNum(result.rewards.coins)} سکه` : ''}
          </div>
        </div>
      </Card>

      {result.topic_breakdown?.length > 0 && (
        <Card>
          <SectionTitle>تفکیک موضوعی</SectionTitle>
          <div className="space-y-1.5">
            {result.topic_breakdown.map((t: any) => (
              <div key={t.node_id} className="flex items-center justify-between text-sm rounded-lg bg-slate-50 px-3 py-2">
                <span className="truncate">{t.title}</span>
                <span className="tabular-nums text-slate-500 shrink-0">
                  <span className="text-emerald-600">{faNum(t.correct)}✓</span>
                  <span className="text-slate-300"> · </span>
                  <span className="text-rose-500">{faNum(t.wrong)}✗</span>
                  <span className="text-slate-300"> · </span>
                  <span className="text-amber-500">{faNum(t.unanswered)}○</span>
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="flex gap-2 justify-center">
        <button className="btn-primary" onClick={onBack}>تست جدید</button>
        {result.wrong + result.unanswered > 0 && (
          <button className="btn-soft" onClick={() => window.location.reload()}>بعداً مرور می‌کنم</button>
        )}
      </div>
    </div>
  )
}

/* --------------------- پرسش مدت بعد از Untimed (V2) --------------------- */

function DurationModal({ sessionId, onClose }: { sessionId: number | null; onClose: () => void }) {
  const { toast } = useApp()
  const [minutes, setMinutes] = useState(30)
  const [saved, setSaved] = useState(false)

  useEffect(() => { if (sessionId !== null) setSaved(false) }, [sessionId])
  if (sessionId === null) return null

  const save = async () => {
    try {
      await api.patch(`/test-sessions/${sessionId}/duration`, { actual_duration_minutes: minutes })
      setSaved(true)
      toast('مدت واقعی ثبت شد — میانگین زمان به‌روز شد')
      setTimeout(onClose, 900)
    } catch (e) { toast(errMessage(e)) }
  }

  return (
    <Modal open={sessionId !== null} onClose={onClose} title="این جلسه چند دقیقه طول کشید؟">
      <div className="space-y-4">
        <InfoBox>جلسهٔ Untimed بود؛ زمان واقعی فقط دادهٔ تحلیلی است و محدودیت نیست.</InfoBox>
        <div className="flex items-center justify-center gap-3">
          <button className="btn-ghost !px-3" onClick={() => setMinutes((m) => Math.max(5, m - 5))}>−۵</button>
          <div className="text-center">
            <div className="text-4xl font-extrabold text-brand-600 tabular-nums">{faNum(minutes)}</div>
            <div className="text-xs text-slate-400">دقیقه</div>
          </div>
          <button className="btn-ghost !px-3" onClick={() => setMinutes((m) => Math.min(300, m + 5))}>+۵</button>
        </div>
        <input type="range" min={5} max={180} step={5} value={minutes} className="w-full accent-brand-600"
          onChange={(e) => setMinutes(+e.target.value)} />
        <button className="btn-primary w-full" onClick={save} disabled={saved}>
          {saved ? '✓ ثبت شد' : 'ثبت'}
        </button>
      </div>
    </Modal>
  )
}
