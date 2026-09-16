import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Card, Chip, EmptyState, ErrorBox, InfoBox, SectionTitle, Spinner } from '../ui'
import { faNum, jalali } from '../jalali'
import { NodeTree } from './Tests'

/** وارد کردن تست‌های قبلی (04_PAST_TEST_IMPORT) — بدون سکه */

export default function ImportPage() {
  const { me, toast } = useApp()
  const [books, setBooks] = useState<any[]>([])
  const [nodes, setNodes] = useState<any[] | null>(null)
  const [testSets, setTestSets] = useState<any[]>([])
  const [sel, setSel] = useState<{ book?: any; node?: any; testSet?: any }>({})
  const [questions, setQuestions] = useState<any[] | null>(null)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [date, setDate] = useState(me?.today.iso ?? '')
  const [err, setErr] = useState<string | null>(null)
  const [done, setDone] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [sessions, setSessions] = useState<any[]>([])

  useEffect(() => {
    api.get('/books').then(setBooks).catch(() => {})
    api.get('/test-sessions', { imported: true }).then(setSessions).catch(() => {})
  }, [])

  const selectBook = (b: any) => {
    setSel({ book: b }); setTestSets([]); setQuestions(null); setDone(null)
    api.get(`/books/${b.id}/nodes`).then(setNodes).catch(() => {})
  }

  const selectNode = async (node: any) => {
    setSel((s) => ({ ...s, node })); setQuestions(null); setDone(null)
    try {
      const sets = await api.get(`/nodes/${node.id}/test-sets`)
      setTestSets(sets)
      const first = sets.find((s: any) => s.test_type === 'normal') ?? sets[0]
      if (first) selectTestSet(first)
    } catch (e) { setErr(errMessage(e)) }
  }

  const selectTestSet = async (ts: any) => {
    setSel((s) => ({ ...s, testSet: ts })); setAnswers({}); setDone(null)
    try {
      const qs = await api.get(`/test-sets/${ts.id}/questions`)
      setQuestions(qs)
    } catch (e) {
      setErr(errMessage(e))
    }
  }

  const setAll = (result: string) => {
    const a: Record<number, string> = {}
    questions?.forEach((q) => { a[q.id] = result })
    setAnswers(a)
  }

  const confirm = async () => {
    if (!sel.testSet || !questions) return
    const entries = Object.entries(answers)
    if (entries.length === 0) { setErr('حداقل یک سوال را مشخص کن.'); return }
    setBusy(true); setErr(null)
    try {
      const res = await api.post('/test-sessions/import', {
        test_set_id: sel.testSet.id,
        date,
        answers: entries.map(([qid, result]) => ({ question_id: +qid, result })),
      })
      setDone(res)
      toast('جلسهٔ گذشته ثبت شد — بدون سکه')
      api.get('/test-sessions', { imported: true }).then(setSessions).catch(() => {})
    } catch (e) { setErr(errMessage(e)) } finally { setBusy(false) }
  }

  if (!me) return <Spinner />

  return (
    <div className="space-y-4 max-w-3xl">
      {err && <ErrorBox message={err} />}

      {done ? (
        <Card>
          <div className="text-center py-6">
            <div className="text-5xl mb-3 anim-pop">📥</div>
            <div className="text-lg font-bold">تست‌های گذشته وارد شد</div>
            <div className="flex justify-center gap-6 mt-4">
              <div><div className="text-2xl font-extrabold text-emerald-600">{faNum(done.correct)}</div><div className="text-xs text-slate-400">درست</div></div>
              <div><div className="text-2xl font-extrabold text-rose-500">{faNum(done.wrong)}</div><div className="text-xs text-slate-400">غلط → صف مرور</div></div>
              <div><div className="text-2xl font-extrabold text-amber-500">{faNum(done.unanswered)}</div><div className="text-xs text-slate-400">نزده</div></div>
            </div>
            <InfoBox color="amber">
              {done.note} Analytics و صف مرور فوراً به‌روز شدند؛ سکه‌ای تعلق نگرفت.
            </InfoBox>
            <button className="btn-primary mt-4" onClick={() => { setDone(null); setAnswers({}) }}>
              وارد کردن جلسهٔ بعدی
            </button>
          </div>
        </Card>
      ) : (
        <Card>
          <SectionTitle>وارد کردن تست‌های قبلی</SectionTitle>
          <InfoBox color="amber">
            قبلاً تست زده‌ای؟ از صفر شروع نکن. نتایج گذشته را وارد کن تا Analytics و صف مرور از همان ابتدا پر شوند.
            سکه بابت تست‌های واردشده تعلق نمی‌گیرد و هیچ attempt ای overwrite نمی‌شود.
          </InfoBox>

          <div className="space-y-4 mt-4">
            <div>
              <span className="text-xs font-medium text-slate-500 mb-1.5 block">کتاب</span>
              <div className="flex flex-wrap gap-2">
                {books.map((b) => (
                  <button key={b.id} onClick={() => selectBook(b)}
                    className={`btn ${sel.book?.id === b.id ? 'bg-brand-600 text-white' : 'btn-ghost'}`}>{b.title}</button>
                ))}
              </div>
            </div>

            {nodes && (
              <div>
                <span className="text-xs font-medium text-slate-500 mb-1.5 block">مبحث</span>
                <NodeTree nodes={nodes} selected={sel.node} onSelect={selectNode} />
              </div>
            )}

            {testSets.length > 0 && (
              <div>
                <span className="text-xs font-medium text-slate-500 mb-1.5 block">مجموعهٔ تست</span>
                <div className="flex flex-wrap gap-2">
                  {testSets.map((ts) => (
                    <button key={ts.id} onClick={() => selectTestSet(ts)}
                      className={`btn ${sel.testSet?.id === ts.id ? 'bg-brand-600 text-white' : 'btn-ghost'}`}>
                      {ts.title} <span className="text-[10px] opacity-60">({faNum(ts.question_count)})</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {questions && (
              <>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="text-xs text-slate-400">
                    {faNum(Object.keys(answers).length)} از {faNum(questions.length)} مشخص‌شده
                  </div>
                  <div className="flex gap-1.5 flex-wrap">
                    <button className="btn-ghost !py-1.5 text-xs" onClick={() => setAll('correct')}>همه درست</button>
                    <button className="btn-ghost !py-1.5 text-xs" onClick={() => setAll('wrong')}>همه غلط</button>
                    <button className="btn-ghost !py-1.5 text-xs" onClick={() => setAll('unanswered')}>همه نزده</button>
                    <button className="btn-ghost !py-1.5 text-xs" onClick={() => setAnswers({})}>پاک‌کردن</button>
                  </div>
                </div>

                <div className="grid grid-cols-4 sm:grid-cols-8 md:grid-cols-10 gap-1.5">
                  {questions.map((q) => (
                    <button key={q.id}
                      onClick={() => setAnswers((a) => ({
                        ...a,
                        [q.id]: a[q.id] === 'correct' ? 'wrong' : a[q.id] === 'wrong' ? 'unanswered' : 'correct',
                      }))}
                      className={`h-9 rounded-lg text-xs font-bold transition
                        ${answers[q.id] === 'correct' ? 'bg-emerald-500 text-white'
                          : answers[q.id] === 'wrong' ? 'bg-rose-500 text-white'
                          : answers[q.id] === 'unanswered' ? 'bg-amber-400 text-white'
                          : 'bg-slate-100 text-slate-400 hover:bg-slate-200'}`}
                      title={`سوال ${q.sequence_no} — کلیک: درست → غلط → نزده`}>
                      {faNum(q.sequence_no)}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <span className="inline-block w-3 h-3 rounded bg-emerald-500" /> درست
                  <span className="inline-block w-3 h-3 rounded bg-rose-500 mr-2" /> غلط
                  <span className="inline-block w-3 h-3 rounded bg-amber-400 mr-2" /> نزده
                </div>

                <label className="block max-w-48">
                  <span className="text-xs font-medium text-slate-500 mb-1 block">تاریخ جلسه (پیش‌فرض امروز)</span>
                  <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
                </label>

                <button className="btn-primary w-full" disabled={busy || Object.keys(answers).length === 0} onClick={confirm}>
                  {busy ? '…' : 'تأیید نهایی و ثبت'}
                </button>
              </>
            )}
          </div>
        </Card>
      )}

      <Card>
        <SectionTitle>جلسه‌های واردشدهٔ قبلی</SectionTitle>
        {sessions.length === 0 ? (
          <EmptyState icon="🗂️" title="هنوز جلسه‌ای وارد نشده" />
        ) : (
          <div className="space-y-1.5">
            {sessions.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span>جلسهٔ #{faNum(s.id)}</span>
                <span className="text-slate-400 text-xs">{jalali(s.session_date ?? s.started_at.slice(0, 10))}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
