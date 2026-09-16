import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { useApp } from '../App'
import { Card, Chip, EmptyState, SectionTitle, Spinner, StatTile } from '../ui'
import { faNum, jalali } from '../jalali'

/** جوایز — سکه، streak، رویدادها، نشان‌ها (07_REWARDS_AND_COINS_V2) */

export default function Rewards() {
  const { me, reloadMe } = useApp()
  const [data, setData] = useState<any>(null)

  const load = () => api.get('/rewards/summary').then((r) => { setData(r); reloadMe() }).catch(() => {})
  useEffect(() => { load() }, [])

  if (!me || !data) return <Spinner />

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile icon="🪙" label="موجودی سکه" value={faNum(data.coins)} color="text-amber-600" />
        <StatTile icon="⭐" label="مجموع امتیاز" value={faNum(data.total_points)} color="text-brand-600" />
        <StatTile icon="🔥" label="Streak فعلی" value={faNum(data.current_streak)} sub={`رکورد: ${faNum(data.longest_streak)}`} color="text-orange-500" />
        <StatTile icon="🏅" label="نشان‌ها" value={faNum(data.badges.length)} color="text-violet-600" />
      </div>

      <Card>
        <SectionTitle>جدول سکه</SectionTitle>
        <div className="grid sm:grid-cols-3 gap-2 text-xs">
          {[
            ['☀️', 'بیدار شدن تا ۰۷:۰۰', '+۱۵'],
            ['🌅', 'قبل از ۰۶:۴۵', '+۵ اضافه'],
            ['✅', 'تکمیل همهٔ تست‌های روز', '+۴۰'],
            ['📌', 'تکمیل Task غیرتست', '+۸'],
            ['✔️', 'هر پاسخ درست', '+۲'],
            ['🔁', 'مرور موفق', '+۳'],
            ['🎯', 'هدف روزانه', '+۲۰'],
            ['🏁', 'هدف هفتگی', '+۷۰'],
            ['🔥', 'هر روز Streak', '+۱۰'],
          ].map(([icon, label, coins]) => (
            <div key={label} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2">
              <span>{icon}</span>
              <span className="flex-1 text-slate-600">{label}</span>
              <span className="font-bold text-amber-600">{coins}</span>
            </div>
          ))}
        </div>
        <div className="text-[11px] text-slate-400 mt-3">
          قانون Streak سخت‌گیرانه است: بیش از یک روز بدون Task تکمیل‌شده → صفر. Import گذشته سکه ندارد.
        </div>
      </Card>

      <Card>
        <SectionTitle>نشان‌ها</SectionTitle>
        {data.badges.length === 0 ? (
          <EmptyState icon="🏅" title="هنوز نشانی نداری" hint="اولین Task را تکمیل کن!" />
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {data.badges.map((b: any) => (
              <div key={b.code} className="rounded-xl border border-amber-100 bg-amber-50/60 p-3 text-center">
                <div className="text-2xl mb-1">🏅</div>
                <div className="text-sm font-bold text-amber-800">{b.title}</div>
                <div className="text-[10px] text-amber-600/70 mt-0.5 leading-relaxed">{b.description}</div>
                <div className="text-[9px] text-slate-400 mt-1">{jalali(b.earned_at.slice(0, 10))}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle>آخرین رویدادها</SectionTitle>
        {data.events.length === 0 ? (
          <EmptyState icon="🗒️" title="هنوز رویدادی نیست" />
        ) : (
          <div className="space-y-1">
            {data.events.slice(0, 25).map((e: any) => (
              <div key={e.id} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="truncate">{e.description}</span>
                <div className="flex items-center gap-2 shrink-0">
                  {e.coins > 0 && <Chip color="amber">🪙 +{faNum(e.coins)}</Chip>}
                  <span className="text-[10px] text-slate-400">{jalali(e.created_at.slice(0, 10))}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
