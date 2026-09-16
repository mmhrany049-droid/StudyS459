import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { useApp } from '../App'
import { Card, Chip, InfoBox, SectionTitle, Spinner, Toggle } from '../ui'
import { faNum, pct } from '../jalali'
import { NodeTree } from './Tests'

/** کتاب‌ها — فعال/غیرفعال‌سازی بدون حذف history (05_BOOK_SYSTEM) */

export default function Books() {
  const { me, toast, reloadMe } = useApp()
  const [books, setBooks] = useState<any[]>([])
  const [sel, setSel] = useState<any>(null)
  const [nodes, setNodes] = useState<any[] | null>(null)
  const [progress, setProgress] = useState<any>(null)
  const [selNode, setSelNode] = useState<any>(null)
  const [parity, setParity] = useState<any>(null)

  const load = () => api.get('/books').then((bs) => {
    setBooks(bs)
    if (!sel && bs.length) select(bs[0])
  }).catch(() => {})
  useEffect(() => { load() }, [])

  const select = (b: any) => {
    setSel(b); setSelNode(null); setParity(null)
    api.get(`/books/${b.id}/nodes`).then(setNodes).catch(() => {})
    api.get(`/progress/books/${b.id}`).then(setProgress).catch(() => {})
  }

  const toggleActive = async (b: any) => {
    if (b.active) {
      await api.del(`/users/me/books/${b.id}/activate`)
      toast('کتاب غیرفعال شد — history حذف نمی‌شود')
    } else {
      await api.post(`/users/me/books/${b.id}/activate`)
      toast('کتاب فعال شد')
    }
    load(); reloadMe()
  }

  const pickNode = async (n: any) => {
    setSelNode(n)
    try { setParity(await api.get(`/nodes/${n.id}/parity-state`)) } catch { setParity(null) }
  }

  if (!me) return <Spinner />

  return (
    <div className="space-y-4">
      <InfoBox>
        فعال/غیرفعال‌کردن کتاب فقط روی استفاده‌های جدید اثر دارد؛ تاریخچهٔ تست‌ها همیشه حفظ می‌شود.
        ساختار کتاب‌ها data-driven است: فصل → درس/عنوان → بخش/زیربخش.
      </InfoBox>

      <div className="grid md:grid-cols-3 gap-4">
        {books.map((b) => (
          <Card key={b.id} className={sel?.id === b.id ? '!border-brand-300' : ''}>
            <div className="flex items-start justify-between gap-2 cursor-pointer" onClick={() => select(b)}>
              <div>
                <div className="font-extrabold">{b.title}</div>
                <div className="text-xs text-slate-400 mt-0.5">انتشارات {b.publisher} · {b.subject}</div>
              </div>
              <Chip color={b.active ? 'green' : 'slate'}>{b.active ? 'فعال' : 'غیرفعال'}</Chip>
            </div>
            <div className="mt-3"><Toggle checked={b.active} onChange={() => toggleActive(b)} label="کتاب فعال باشد" /></div>
          </Card>
        ))}
      </div>

      {sel && (
        <Card>
          <SectionTitle extra={progress && <div className="flex gap-2">
            <Chip color="blue">پوشش {pct(progress.stats.coverage)}</Chip>
            <Chip color="green">دقت {pct(progress.stats.accuracy)}</Chip>
            <Chip>{faNum(progress.stats.volume)} تلاش</Chip>
          </div>}>
            ساختار {sel.title}
          </SectionTitle>
          {nodes ? (
            <div className="grid md:grid-cols-2 gap-4">
              <NodeTree nodes={nodes} selected={selNode} onSelect={pickNode} />
              <div>
                {selNode ? (
                  <div className="rounded-xl bg-slate-50 p-4 space-y-2 text-sm sticky top-20">
                    <div className="font-bold">{selNode.title}</div>
                    <div className="text-xs text-slate-400">{selNode.node_type === 'chapter' ? 'فصل' :
                      selNode.node_type === 'lesson' ? 'درس' : selNode.node_type === 'title' ? 'عنوان' :
                        selNode.node_type === 'section' ? 'بخش' : 'زیربخش'} · کد {selNode.code}</div>
                    {parity && (
                      <div className="text-xs text-slate-500 bg-white rounded-lg p-3 border border-slate-100">
                        آخرین parity: <b>{parity.last_parity === 'odd' ? 'فرد' : parity.last_parity === 'even' ? 'زوج' : '—'}</b>
                        <br />پیشنهاد بعدی: <b className="text-brand-600">{parity.suggested_next === 'odd' ? 'فرد' : 'زوج'}</b>
                      </div>
                    )}
                    <button className="btn-soft w-full" onClick={() => window.dispatchEvent(new CustomEvent('goto-tests'))}
                      style={{ display: 'none' }}>—</button>
                  </div>
                ) : (
                  <div className="text-sm text-slate-400 text-center py-8">
                    یک مبحث از درخت انتخاب کن تا جزئیاتش را ببینی
                  </div>
                )}
              </div>
            </div>
          ) : <Spinner />}
        </Card>
      )}
    </div>
  )
}
