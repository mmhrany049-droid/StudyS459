import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Bar, Card, Chip, EmptyState, ErrorBox, SectionTitle, Spinner, StatTile } from '../ui'
import { faNum, jalali, pct } from '../jalali'

/** پیشرفت — Coverage ≠ Accuracy ≠ Volume (07_ANALYTICS_V1) */

export default function Progress() {
  const { me } = useApp()
  const [overview, setOverview] = useState<any>(null)
  const [books, setBooks] = useState<any[]>([])
  const [bookId, setBookId] = useState<number | null>(null)
  const [bookData, setBookData] = useState<any>(null)
  const [weaknesses, setWeaknesses] = useState<any[]>([])
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.get('/progress/overview').then(setOverview).catch((e) => setErr(errMessage(e)))
    api.get('/books').then((bs) => {
      setBooks(bs)
      if (bs.length) { setBookId(bs[0].id) }
    }).catch(() => {})
    api.get('/analytics/weaknesses', { limit: 8 }).then(setWeaknesses).catch(() => {})
  }, [])

  useEffect(() => {
    if (bookId) api.get(`/progress/books/${bookId}`).then(setBookData).catch(() => {})
    else setBookData(null)
  }, [bookId])

  if (!me) return <Spinner />

  const maxTrend = Math.max(1, ...(overview?.trend ?? []).map((t: any) => t.correct + t.wrong + t.unanswered))

  return (
    <div className="space-y-4">
      {err && <ErrorBox message={err} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile icon="📦" label="حجم (Volume)" value={faNum(overview?.volume ?? 0)} sub="کل تلاش‌ها" />
        <StatTile icon="🎯" label="دقت (Accuracy)" value={pct(overview?.accuracy)} sub="در پاسخ‌های داده‌شده" color="text-emerald-600" />
        <StatTile icon="🗺️" label="پوشش (Coverage)" value={pct(overview?.coverage)} sub="سوالات حداقل یک‌بار دیده‌شده" color="text-brand-600" />
        <StatTile icon="🧪" label="جلسات" value={faNum(overview?.sessions ?? 0)} sub={`شامل ${faNum(overview?.imported_sessions ?? 0)} واردشده`} color="text-violet-600" />
      </div>

      {/* روند روزانه */}
      <Card>
        <SectionTitle>روند ۱۴ روز اخیر</SectionTitle>
        {overview?.trend?.every((t: any) => t.correct + t.wrong + t.unanswered === 0) ? (
          <EmptyState icon="📈" title="هنوز داده‌ای نیست" hint="با تست زدن یا وارد کردن تست گذشته شروع کن" />
        ) : (
          <div className="flex items-end gap-1.5 h-36" dir="ltr">
            {overview.trend.map((t: any) => {
              const total = t.correct + t.wrong + t.unanswered
              return (
                <div key={t.date} className="flex-1 flex flex-col justify-end items-center gap-0.5 group relative">
                  <div className="w-full rounded-t-md overflow-hidden flex flex-col justify-end" style={{ height: `${(total / maxTrend) * 100}%` }}>
                    {total > 0 && (
                      <>
                        <div className="bg-amber-300" style={{ height: `${(t.unanswered / total) * 100}%` }} />
                        <div className="bg-rose-400" style={{ height: `${(t.wrong / total) * 100}%` }} />
                        <div className="bg-emerald-500" style={{ height: `${(t.correct / total) * 100}%` }} />
                      </>
                    )}
                  </div>
                  <div className="absolute -top-8 hidden group-hover:block bg-slate-800 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap z-10">
                    {jalali(t.date)}: {faNum(t.correct)}✓ {faNum(t.wrong)}✗ {faNum(t.unanswered)}○
                  </div>
                </div>
              )
            })}
          </div>
        )}
        <div className="flex gap-3 justify-center mt-2 text-[11px] text-slate-400">
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500" /> درست
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-rose-400" /> غلط
          <span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-300" /> نزده
        </div>
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        {/* جدول کتاب */}
        <Card className="md:col-span-2">
          <SectionTitle extra={
            <div className="flex gap-1.5 flex-wrap">
              {books.map((b) => (
                <button key={b.id} onClick={() => setBookId(b.id)}
                  className={`btn ${bookId === b.id ? 'bg-brand-600 text-white' : 'btn-ghost'} !py-1.5 !px-3 text-xs`}>
                  {b.title}
                </button>
              ))}
            </div>
          }>
            جدول پوشش و دقت
          </SectionTitle>
          {!bookData ? <Spinner /> : (
            <div className="text-sm">
              <div className="flex gap-4 mb-3 flex-wrap">
                <Chip color="blue">پوشش کتاب: {pct(bookData.stats.coverage)}</Chip>
                <Chip color="green">دقت: {pct(bookData.stats.accuracy)}</Chip>
                <Chip>حجم: {faNum(bookData.stats.volume)}</Chip>
              </div>
              <NodeTable nodes={bookData.tree} depth={0} />
            </div>
          )}
        </Card>

        {/* ضعف‌ها */}
        <Card className="md:col-span-2">
          <SectionTitle>مباحث ضعیف</SectionTitle>
          {weaknesses.length === 0 ? (
            <EmptyState icon="🛡️" title="ضعف شناسایی‌شده‌ای نیست" hint="حداقل ۳ تلاش روی هر مبحث لازم است" />
          ) : (
            <div className="space-y-2">
              {weaknesses.map((w) => (
                <div key={w.node_id} className="rounded-xl border border-slate-100 p-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="font-medium text-sm">
                      {w.subject && <Chip color="violet">{w.subject}</Chip>} {w.title}
                    </div>
                    <div className="flex gap-1.5">
                      <Chip color={w.accuracy >= 0.6 ? 'green' : 'red'}>دقت {pct(w.accuracy)}</Chip>
                      <Chip color={w.unanswered > 0 ? 'amber' : 'slate'}>{faNum(w.unanswered)} نزده</Chip>
                    </div>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <div>
                      <div className="text-[10px] text-slate-400 mb-0.5">پوشش {pct(w.coverage)}</div>
                      <Bar value={w.coverage} color="bg-brand-400" className="!h-1.5" />
                    </div>
                    <div>
                      <div className="text-[10px] text-slate-400 mb-0.5">نرخ خطا {pct(w.error_rate)}</div>
                      <Bar value={w.error_rate} color="bg-rose-400" className="!h-1.5" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function NodeTable({ nodes, depth }: { nodes: any[]; depth: number }) {
  const [open, setOpen] = useState<Record<number, boolean>>({})
  return (
    <div>
      {nodes.map((n) => {
        const hasData = n.attempted > 0
        return (
          <div key={n.id}>
            <div className="flex items-center gap-2 py-1.5 border-b border-slate-50 hover:bg-slate-50/50 rounded px-1"
              style={{ paddingRight: depth * 12 }}>
              {n.children?.length > 0 ? (
                <button className="text-slate-300 hover:text-brand-500 w-4 text-xs"
                  onClick={() => setOpen((o) => ({ ...o, [n.id]: !o[n.id] }))}>
                  {open[n.id] ? '▾' : '◂'}
                </button>
              ) : <span className="w-4" />}
              <span className={`flex-1 truncate ${depth === 0 ? 'font-bold' : 'text-slate-600'}`}>{n.title}</span>
              <span className="hidden sm:flex items-center gap-2 text-[11px] text-slate-400 tabular-nums w-40">
                <span title="پوشش">🗺️ {pct(n.coverage)}</span>
                <span title="دقت">🎯 {pct(n.accuracy)}</span>
                <span title="تلاش">📦 {faNum(n.volume)}</span>
              </span>
              <span className={`w-14 h-1.5 rounded-full overflow-hidden bg-slate-100 hidden sm:block`}>
                <span className={`block h-full ${hasData ? 'bg-brand-500' : ''}`} style={{ width: `${n.coverage * 100}%` }} />
              </span>
            </div>
            {open[n.id] && n.children?.length > 0 && <NodeTable nodes={n.children} depth={depth + 1} />}
          </div>
        )
      })}
    </div>
  )
}
