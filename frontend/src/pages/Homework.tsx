import { useEffect, useState } from 'react'
import { academicAPI } from '../api/client'

export default function Homework() {
  const [homeworks, setHomeworks] = useState<any[]>([])
  const [form, setForm] = useState({ title: '', description: '', due_date: '', estimated_time_minutes: 30, priority: 0, source: 'manual' })
  const [loading, setLoading] = useState(true)

  const load = () => {
    academicAPI.homework.list().then(res=>{ setHomeworks(res.data); setLoading(false) })
  }
  useEffect(()=>{ load() },[])

  const handleCreate = async (e: React.FormEvent)=>{
    e.preventDefault()
    try{
      await academicAPI.homework.create(form)
      setForm({ title: '', description: '', due_date: '', estimated_time_minutes: 30, priority: 0, source: 'manual' })
      load()
    }catch(err){ console.error(err) }
  }

  const handleStatus = async (id:number, status:string)=>{
    await academicAPI.homework.update(id,{status})
    load()
  }

  if(loading) return <div>در حال بارگذاری...</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">تکالیف</h1>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">افزودن تکلیف</h2>
        <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
          <input value={form.title} onChange={e=>setForm({...form,title:e.target.value})} placeholder="عنوان تکلیف" className="border rounded px-3 py-2" required />
          <input type="date" value={form.due_date} onChange={e=>setForm({...form,due_date:e.target.value})} className="border rounded px-3 py-2" />
          <input value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="توضیحات" className="border rounded px-3 py-2 col-span-2" />
          <input type="number" value={form.estimated_time_minutes} onChange={e=>setForm({...form,estimated_time_minutes:Number(e.target.value)})} placeholder="زمان تقریبی دقیقه" className="border rounded px-3 py-2" />
          <select value={form.source} onChange={e=>setForm({...form,source:e.target.value})} className="border rounded px-3 py-2">
            <option value="manual">دستی</option>
            <option value="school">مدرسه</option>
            <option value="external_class">کلاس خارجی</option>
          </select>
          <button type="submit" className="col-span-2 bg-blue-600 text-white py-2 rounded hover:bg-blue-700">افزودن - به صورت خودکار تسک برنامه‌ریز می‌سازد</button>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">لیست تکالیف</h2>
        <div className="space-y-3">
          {homeworks.map(hw=>(
            <div key={hw.id} className="border rounded-lg p-4 flex justify-between">
              <div>
                <p className="font-medium">{hw.title}</p>
                <p className="text-sm text-gray-600">{hw.description}</p>
                <p className="text-xs text-gray-500">مهلت: {hw.due_date || 'ندارد'} - منبع: {hw.source} - {hw.estimated_time_minutes} دقیقه</p>
                {hw.task_id && <p className="text-xs text-blue-600">✓ تسک برنامه‌ریز ساخته شد (ID: {hw.task_id})</p>}
              </div>
              <div className="flex flex-col gap-2">
                <span className={`text-xs px-2 py-1 rounded ${hw.status==='completed'?'bg-green-100 text-green-700':'bg-yellow-100 text-yellow-700'}`}>{hw.status}</span>
                <select value={hw.status} onChange={e=>handleStatus(hw.id,e.target.value)} className="text-xs border rounded px-2 py-1">
                  <option value="pending">در انتظار</option>
                  <option value="in_progress">در حال انجام</option>
                  <option value="completed">تکمیل شده</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
