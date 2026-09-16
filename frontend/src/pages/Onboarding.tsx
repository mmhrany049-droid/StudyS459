import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Bar, Card, Chip, InfoBox, SectionTitle, Spinner } from '../ui'
import { faNum } from '../jalali'

/** پرسشنامهٔ تطبیقی V2.1 — انتخاب سؤال بعدی بر اساس uncertainty */

export default function Onboarding() {
  const { me, toast } = useApp()
  const [state, setState] = useState<'loading' | 'question' | 'done'>('loading')
  const [q, setQ] = useState<any>(null)
  const [summary, setSummary] = useState<any>(null)
  const [model, setModel] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const next = async () => {
    setBusy(true); setErr(null)
    try {
      const r = await api.post('/onboarding/questions/next')
      setSummary(r.summary)
      if (r.complete) {
        setState('done')
        api.get('/user-model').then(setModel).catch(() => {})
        await api.post('/onboarding/finish')
      } else {
        setQ(r.question)
        setState('question')
      }
    } catch (e) { setErr(errMessage(e)) } finally { setBusy(false) }
  }

  useEffect(() => {
    api.get('/onboarding/summary').then((s) => {
      setSummary(s)
      api.get('/user-model').then(setModel).catch(() => {})
      if (s.complete) setState('done')
      else next()
    }).catch(() => setState('question'))
  }, [])

  const answer = async (value: any) => {
    if (busy) return
    setBusy(true)
    try {
      const r = await api.post('/onboarding/answers', { question_key: q.key, answer: value })
      setSummary(r.summary)
      api.get('/user-model').then(setModel).catch(() => {})
      setTimeout(next, 250)
    } catch (e) { setErr(errMessage(e)); setBusy(false) }
  }

  if (!me || state === 'loading') return <Spinner />

  return (
    <div className="max-w-2xl space-y-4">
      {err && <div className="rounded-xl bg-rose-50 border border-rose-100 text-rose-600 text-sm px-4 py-3">{err}</div>}

      {summary && (
        <div>
          <div className="flex justify-between text-xs text-slate-400 mb-1">
            <span>پیشرفت پرسشنامهٔ شناخت</span>
            <span className="tabular-nums">{faNum(summary.answered)} از {faNum(summary.total)}</span>
          </div>
          <Bar value={summary.answered / summary.total} color="bg-violet-500" />
        </div>
      )}

      {state === 'question' && q && (
        <Card key={q.key}>
          <div className="text-xs text-violet-500 font-medium mb-2">{q.group}</div>
          <div className="text-lg font-bold leading-relaxed mb-5">{q.text}</div>

          {q.type === 'scale' ? (
            <div className="flex gap-2 justify-center">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} disabled={busy} onClick={() => answer(n)}
                  className="flex-1 max-w-20 aspect-square rounded-2xl bg-slate-50 hover:bg-brand-100 border border-slate-100
                    text-xl font-extrabold text-slate-600 hover:text-brand-700 transition cursor-pointer">
                  {faNum(n)}
                </button>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {q.options.map((o: any) => (
                <button key={o.key} disabled={busy} onClick={() => answer(o.key)}
                  className="w-full text-right rounded-xl border border-slate-100 hover:border-brand-300 hover:bg-brand-50/50
                    px-4 py-3 text-sm transition cursor-pointer">
                  {o.text}
                </button>
              ))}
            </div>
          )}
          <div className="text-[11px] text-slate-400 mt-4 text-center">
            سؤال بعدی بر اساس جاهایی انتخاب می‌شود که کمترین اطمینان را داریم.
          </div>
        </Card>
      )}

      {state === 'done' && (
        <>
          <Card>
            <div className="text-center py-4">
              <div className="text-5xl mb-2 anim-pop">🧭</div>
              <div className="text-lg font-bold">پرسشنامه کامل شد!</div>
              <div className="text-sm text-slate-400 mt-1">
                مدل کاربر با confidence ذخیره شد — هر بعد با شواهد رفتاری واقعی به‌تدریج دقیق‌تر می‌شود.
              </div>
            </div>
          </Card>
        </>
      )}

      {model && <PersonalityView model={model} />}
    </div>
  )
}

export function PersonalityView({ model }: { model: any }) {
  const dims = Object.entries(model.personality ?? {}) as [string, any][]
  return (
    <Card>
      <SectionTitle extra={<Chip color="violet">نسخهٔ {faNum(model.version)}</Chip>}>
        مدل کاربر — شخصیت (Self-Report)
      </SectionTitle>
      <InfoBox color="violet">
        همهٔ امتیازها ۰ تا ۱ و همراه confidence ذخیره می‌شوند. یک پاسخ منفرد هیچ ویژگی را قطعی نمی‌کند و
        self-report جدا از رفتار مشاهده‌شده نگه داشته می‌شود.
      </InfoBox>
      <div className="space-y-3 mt-4">
        {dims.map(([k, d]) => (
          <div key={k}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-600 font-medium">{d.label}</span>
              <span className="text-slate-400 tabular-nums">
                {faNum(Math.round(d.value * 100))}٪
                <span className="text-slate-300"> · اطمینان {faNum(Math.round(d.confidence * 100))}٪ · {faNum(d.evidence_count)} شاهد</span>
              </span>
            </div>
            <div className="flex gap-1">
              <Bar value={d.value} color="bg-violet-500" className="flex-1" />
              <Bar value={d.confidence} color="bg-slate-300" className="w-16" />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
