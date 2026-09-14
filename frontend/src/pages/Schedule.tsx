import { useEffect, useState } from 'react'
import { academicAPI, booksAPI } from '../api/client'

export default function Schedule() {
  const [schedules, setSchedules] = useState<any[]>([])
  const [form, setForm] = useState({ title: '', schedule_type: 'school', day_of_week: 'saturday', start_time: '08:00', end_time: '09:00' })
  const [loading, setLoading] = useState(true)

  const load = () => {
    academicAPI.schedules.list().then(res => {
      setSchedules(res.data)
      setLoading(false)
    })
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await academicAPI.schedules.create(form)
      setForm({ title: '', schedule_type: 'school', day_of_week: 'saturday', start_time: '08:00', end_time: '09:00' })
      load()
    } catch (err) { console.error(err) }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('حذف شود؟')) return
    await academicAPI.schedules.delete(id)
    load()
  }

  const days = ['saturday','sunday','monday','tuesday','wednesday','thursday','friday']
  const persianDays: Record<string,string> = { saturday:'شنبه', sunday:'یکشنبه', monday:'دوشنبه', tuesday:'سه‌شنبه', wednesday:'چهارشنبه', thursday:'پنجشنبه', friday:'جمعه' }

  if (loading) return <div>در حال بارگذاری...</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">برنامه درسی و کلاسی</h1>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">افزودن برنامه</h2>
        <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
          <input value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="عنوان" className="border rounded px-3 py-2" required />
          <select value={form.schedule_type} onChange={e=>setForm({...form,schedule_type:e.target.value})} className="border rounded px-3 py-2">
            <option value="school">مدرسه</option>
            <option value="external_class">کلاس خارجی</option>
            <option value="busy">مشغول</option>
            <option value="study_block">بلوک مطالعه</option>
          </select>
          <select value={form.day_of_week} onChange={e=>setForm({...form,day_of_week:e.target.value})} className="border rounded px-3 py-2">
            {days.map(d=> <option key={d} value={d}>{persianDays[d]}</option>)}
          </select>
          <div className="flex gap-2">
            <input type="time" value={form.start_time} onChange={e=>setForm({...form,start_time:e.target.value})} className="border rounded px-3 py-2 flex-1" />
            <input type="time" value={form.end_time} onChange={e=>setForm({...form,end_time:e.target.value})} className="border rounded px-3 py-2 flex-1" />
          </div>
          <button type="submit" className="col-span-2 bg-blue-600 text-white py-2 rounded hover:bg-blue-700">افزودن</button>
        </form>
      </div>

      <div className="grid grid-cols-7 gap-4">
        {days.map(day=> (
          <div key={day} className="bg-white rounded-lg shadow p-3">
            <h3 className="font-bold text-sm text-center mb-3">{persianDays[day]}</h3>
            <div className="space-y-2">
              {schedules.filter(s=>s.day_of_week===day).map(s=> (
                <div key={s.id} className="text-xs p-2 bg-gray-50 rounded border">
                  <p className="font-medium">{s.title}</p>
                  <p>{s.start_time}-{s.end_time}</p>
                  <p className="text-gray-500">{s.schedule_type}</p>
                  <button onClick={()=>handleDelete(s.id)} className="text-red-600 text-xs mt-1">حذف</button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-blue-50 p-4 rounded-lg text-sm">
        <p>این برنامه‌ها برای محاسبه ظرفیت روزانه استفاده می‌شوند. هرچه ساعات مدرسه/کلاس بیشتر باشد، ظرفیت مطالعه کمتر است.</p>
      </div>
    </div>
  )
}
