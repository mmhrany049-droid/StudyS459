import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Bar, Card, Chip, EmptyState, ErrorBox, InfoBox, SectionTitle, Spinner, StatTile } from '../ui'
import { faNum, pct } from '../jalali'

/** مرور — خوشهٔ موضوعی نزدیک + ترتیب تصادفی (سند 06 V2) */

export default function Review() {
  const { me, toast, reloadMe } = useApp()
  const [summary, setSummary] = useState<any>(null)
  const [session, setSession] = useState<any>(null)
  const [result, setResult] = useState<any>(null)
  const [err, setErr] = useState<string | null>(null)
  const [idx, setIdx] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})

  const load = () => { api.get('/review/summary').then(setSummary).catch(() => {}) }
  useEffect(load, [])

  const start = async () => {
    setErr(null)
    try {
      const s = await api.post('/review-sessions', {})
      setSession(s); setIdx(0); setAnswers({}); setResult(null)
    } catch (e) { setErr(errMessage(e)) }
  }

  const answer = async (res: 'correct' | 'wrong') => {
    const q = session.questions[idx]
    if (answers[q.id]) return
    setAnswers((a) => ({ ...a, [q.id]: res }))
    try {
      await api.post(`/review-sessions/${session.id}/answers`, { question_id: q.id, result: res })
      if (res === 'correct') toast('✓ مرور موفق — +۳ سکه و خروج از صف')
      else toast('✗ دوباره غلط — اولویت بالا و بازگشت زودتر')
    } catch (e) { toast(errMessage(e)) }
    setTimeout(() => {
      if (idx < session.questions.length - 1) setIdx((i) => i + 1)
      else finish()
    }, 500)
  }

  const finish = async () => {
    try {
      const res = await api.post(`/review-sessions/${session.id}/finish`)
      setResult(res); setSession(null); reloadMe(); load()
    } catch (e) { toast(errMessage(e)) }
  }

  if (!me) return null

  if (session) {
    const q = session.questions[idx]
    return (
      <div className="max-w-2xl space-y-4">
        <InfoBox color="violet">
          جلسهٔ مرور: سوالات از یک خوشهٔ موضوعی نزدیک انتخاب و ترتیب نمایش تصادفی است.
          parity و بازه اعمال نمی‌شود — هدف، دیدن دوبارهٔ ضعف است.
        </InfoBox>
        <Bar value={(idx + 1) / session.questions.length} color="bg-violet-500" />
        <Card className="text-center py-10">
          <div className="text-slate-400 text-sm mb-1">مرور — سوال {faNum(idx + 1)} از {faNum(session.questions.length)}</div>
          <div className="text-3xl font-extrabold text-slate-700 mb-6">{faNum(q.sequence_no)}</div>
          <div className="flex justify-center gap-3">
            <button className="btn-success !px-8 !py-3" disabled={!!answers[q.id]}
              onClick={() => answer('correct')}>✓ الان درست بلدم</button>
            <button className="btn-danger !px-8 !py-3" disabled={!!answers[q.id]}
              onClick={() => answer('wrong')}>✗ هنوز بلد نیستم</button>
          </div>
          {answers[q.id] && (
            <div className="mt-5 anim-pop">
              <Chip color={answers[q.id] === 'correct' ? 'green' : 'red'}>
                {answers[q.id] === 'correct' ? 'خارج از صف مرور' : 'در صف با اولویت بالاتر'}
              </Chip>
            </div>
          )}
        </Card>
        <div className="flex gap-1.5 flex-wrap justify-center">
          {session.questions.map((qq: any, i: number) => (
            <span key={qq.id} className={`w-7 h-7 rounded-lg text-[11px] font-bold flex items-center justify-center
              ${i === idx ? 'bg-violet-600 text-white'
                : answers[qq.id] === 'correct' ? 'bg-emerald-100 text-emerald-600'
                : answers[qq.id] === 'wrong' ? 'bg-rose-100 text-rose-500'
                : 'bg-slate-100 text-slate-400'}`}>
              {faNum(i + 1)}
            </span>
          ))}
        </div>
      </div>
    )
  }

  if (result) {
    return (
      <div className="max-w-2xl space-y-4">
        <Card className="text-center py-6">
          <div className="text-4xl mb-2">🔁</div>
          <div className="text-lg font-bold">جلسهٔ مرور تمام شد</div>
          <div className="flex justify-center gap-6 mt-4">
            <div><div className="text-2xl font-extrabold text-emerald-600">{faNum(result.correct)}</div><div className="text-xs text-slate-400">حل‌شده</div></div>
            <div><div className="text-2xl font-extrabold text-rose-500">{faNum(result.wrong)}</div><div className="text-xs text-slate-400">هنوز غلط</div></div>
          </div>
        </Card>
        <div className="flex justify-center gap-2">
          <button className="btn-primary" onClick={() => { setResult(null); start() }}>مرور بعدی</button>
          <button className="btn-ghost" onClick={() => setResult(null)}>بازگشت</button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 max-w-2xl">
      {err && <ErrorBox message={err} />}
      <div className="grid grid-cols-3 gap-3">
        <StatTile icon="⏳" label="در صف مرور" value={faNum(summary?.pending ?? 0)} />
        <StatTile icon="🔴" label="بحرانی (غلط ≥۲)" value={faNum(summary?.critical ?? 0)} color="text-rose-500" />
        <StatTile icon="⏰" label="مهلت رسیده" value={faNum(summary?.due ?? 0)} color="text-amber-500" />
      </div>

      <Card>
        <SectionTitle>جلسهٔ مرور</SectionTitle>
        {(summary?.pending ?? 0) === 0 ? (
          <EmptyState icon="🎉" title="صف مرور خالی است!"
            hint="غلط‌ها و نزده‌های تست‌های بعدی اینجا جمع می‌شوند" />
        ) : (
          <div className="space-y-4">
            <InfoBox color="violet">
              قوانین: حداکثر {faNum(25)} سوال در هر جلسه · خوشهٔ موضوعی (حداقل {faNum(8)}) ·
              بحرانی‌ها حداکثر تا {faNum(2)} روز و عادی‌ها تا {faNum(3)} روز بازگشت · پنج‌شنبه/جمعه وزن مرور بالاتر
            </InfoBox>
            <button className="btn-primary w-full !py-3" onClick={start}>
              🔁 شروع جلسهٔ مرور
            </button>
          </div>
        )}
      </Card>
    </div>
  )
}
