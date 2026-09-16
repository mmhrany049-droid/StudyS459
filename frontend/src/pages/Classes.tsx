import React, { useEffect, useState } from 'react'
import { api, errMessage } from '../api'
import { useApp } from '../App'
import { Card, Chip, EmptyState, ErrorBox, InfoBox, SectionTitle, Spinner } from '../ui'
import { faNum, IRAN_WEEKDAYS, jalali } from '../jalali'

/** کلاس‌ها و برنامهٔ هفتگی — کلاس‌های پیش‌فرض V2 + override مدرسه */

export default function Classes() {
  const { me, toast } = useApp()
  const [schedules, setSchedules] = useState<any[]>([])
  const [subjects, setSubjects] = useState<any[]>([])
  const [overrides, setOverrides] = useState<any[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [form, setForm] = useState({ title: '', subject_id: '' as number | '', day: '' as number | '', start: '', end: '' })
  const [ovForm, setOvForm] = useState({ date: me?.today.iso ?? '', is_school_day: false, reason: '' })

  const load = () => {
    api.get('/schedules').then(setSchedules).catch(() => {})
    api.get('/subjects').then(setSubjects).catch(() => {})
    api.get('/school-day-overrides').then(setOverrides).catch(() => {})
  }
  useEffect(load, [])

  if (!me) return <Spinner />

  const act = async (fn: () => Promise<any>, msg: string) => {
    try { await fn(); toast(msg); load() } catch (e) { setErr(errMessage(e)) }
  }

  const seedDefaults = () => act(() => api.post('/schedules/seed-defaults'), 'کلاس‌های پیش‌فرض حسابان/شیمی/فیزیک ساخته شدند — روز و ساعت را تکمیل کن')

  const addClass = () => {
    if (!form.title.trim()) return
    act(() => api.post('/schedules', {
      title: form.title.trim(),
      subject_id: form.subject_id === '' ? null : form.subject_id,
      day_of_week: form.day === '' ? null : form.day,
      start_time: form.start || null, end_time: form.end || null,
    }), 'کلاس اضافه شد').then(() => setForm({ title: '', subject_id: '', day: '', start: '', end: '' }))
  }

  const hasDefaults = schedules.some((s) => s.source === 'default_seed_v2')

  return (
    <div className="space-y-4 max-w-4xl">
      {err && <ErrorBox message={err} />}

      <Card>
        <SectionTitle extra={!hasDefaults && <button className="btn-soft !py-1.5 text-xs" onClick={seedDefaults}>
          + افزودن کلاس‌های پیش‌فرض
        </button>}>
          کلاس‌های تقویتی
        </SectionTitle>
        <InfoBox>
          در روزهایی که کلاس داری، کاندیدهای تست همان درس <b>+۱۵ امتیاز</b> اولویت می‌گیرند و
          ظرفیت آن روز به اندازهٔ مدت کلاس کم می‌شود.
        </InfoBox>
        {schedules.length === 0 ? (
          <EmptyState icon="🏫" title="کلاسی ثبت نشده"
            hint="سه کلاس پیش‌فرض (حسابان، شیمی، فیزیک) را اضافه کن یا کلاس دلخواه بساز" />
        ) : (
          <div className="space-y-2 mt-3">
            {schedules.map((s) => (
              <div key={s.id} className="rounded-xl border border-slate-100 p-3 flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <div className="font-medium text-sm flex items-center gap-2">
                    {s.title}
                    {s.source === 'default_seed_v2' && <Chip color="violet">پیش‌فرض</Chip>}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {s.day_of_week !== null ? IRAN_WEEKDAYS[s.day_of_week] : 'روز مشخص نیست'}
                    {s.start_time && s.end_time ? ` · ${s.start_time} تا ${s.end_time}` : ' · ساعت مشخص نیست'}
                    {s.subject ? ` · ${s.subject}` : ''}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <select className="input !w-28 !py-1.5 text-xs" value={s.day_of_week ?? ''} disabled={s.day_of_week === null && false}
                    onChange={(e) => act(() => api.patch(`/schedules/${s.id}`, {
                      title: s.title, subject_id: s.subject_id,
                      day_of_week: e.target.value === '' ? null : +e.target.value,
                      start_time: s.start_time, end_time: s.end_time,
                    }), 'روز کلاس به‌روز شد')}>
                    <option value="">— روز —</option>
                    {IRAN_WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                  </select>
                  <input type="time" className="input !w-24 !py-1.5 text-xs" defaultValue={s.start_time ?? ''}
                    onBlur={(e) => act(() => api.patch(`/schedules/${s.id}`, {
                      title: s.title, subject_id: s.subject_id, day_of_week: s.day_of_week,
                      start_time: e.target.value || null, end_time: s.end_time,
                    }), 'ساعت شروع به‌روز شد')} />
                  <input type="time" className="input !w-24 !py-1.5 text-xs" defaultValue={s.end_time ?? ''}
                    onBlur={(e) => act(() => api.patch(`/schedules/${s.id}`, {
                      title: s.title, subject_id: s.subject_id, day_of_week: s.day_of_week,
                      start_time: s.start_time, end_time: e.target.value || null,
                    }), 'ساعت پایان به‌روز شد')} />
                  <button className="btn-danger !py-1.5 !px-2.5 text-xs"
                    onClick={() => act(() => api.del(`/schedules/${s.id}`), 'کلاس حذف شد')}>حذف</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle>کلاس جدید</SectionTitle>
        <div className="grid sm:grid-cols-5 gap-3">
          <input className="input sm:col-span-2" placeholder="عنوان کلاس" value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <select className="input" value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value === '' ? '' : +e.target.value })}>
            <option value="">— درس —</option>
            {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select className="input" value={form.day} onChange={(e) => setForm({ ...form, day: e.target.value === '' ? '' : +e.target.value })}>
            <option value="">— روز —</option>
            {IRAN_WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
          <div className="flex gap-1.5">
            <input type="time" className="input" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} />
            <input type="time" className="input" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} />
          </div>
        </div>
        <button className="btn-primary mt-3" onClick={addClass}>افزودن کلاس</button>
      </Card>

      <Card>
        <SectionTitle>Override روز مدرسه</SectionTitle>
        <InfoBox color="amber">
          «امروز مدرسه نمی‌روم»: ظرفیت آن روز ×۱٫۳۵ (حداقل ۱۸۰ دقیقه). فصل تابستان هم به‌طور خودکار
          حالت تعطیلات است (ظرفیت کامل‌تر) — از تنظیمات قابل تغییر است.
        </InfoBox>
        <div className="flex flex-wrap items-end gap-3 mt-3">
          <label className="block">
            <span className="text-xs font-medium text-slate-500 mb-1 block">تاریخ</span>
            <input type="date" className="input" value={ovForm.date} onChange={(e) => setOvForm({ ...ovForm, date: e.target.value })} />
          </label>
          <label className="flex items-center gap-2 text-sm pb-2.5 cursor-pointer">
            <input type="checkbox" className="accent-brand-600 w-4 h-4" checked={ovForm.is_school_day}
              onChange={(e) => setOvForm({ ...ovForm, is_school_day: e.target.checked })} />
            روز مدرسه است
          </label>
          <input className="input flex-1 min-w-40" placeholder="دلیل (اختیاری)" value={ovForm.reason}
            onChange={(e) => setOvForm({ ...ovForm, reason: e.target.value })} />
          <button className="btn-primary"
            onClick={() => act(() => api.post('/school-day-overrides', ovForm), 'Override ثبت شد')}>ثبت</button>
        </div>
        {overrides.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {overrides.map((o) => (
              <div key={o.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span>{jalali(o.date)} — {o.is_school_day ? 'روز مدرسه' : 'مدرسه نمی‌روم'}</span>
                <span className="text-xs text-slate-400">{o.reason}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
