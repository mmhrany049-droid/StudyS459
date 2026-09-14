import { useEffect, useState } from 'react'
import { academicAPI } from '../api/client'

export default function Exams() {
  const [exams, setExams] = useState<any[]>([])
  const [form, setForm] = useState({ name: '', exam_type: 'school', exam_date: new Date().toISOString().split('T')[0], provider: '', total_questions: 20, correct_count: 0, wrong_count: 0, unanswered_count: 0 })
  const [loading, setLoading] = useState(true)

  const load = () => {
    academicAPI.exams.list().then(res=>{ setExams(res.data); setLoading(false) })
  }
  useEffect(()=>{ load() },[])

  const handleCreate = async (e: React.FormEvent)=>{
    e.preventDefault()
    try{
      await academicAPI.exams.create(form)
      load()
    }catch(err){ console.error(err) }
  }

  if(loading) return <div>در حال بارگذاری...</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">امتحانات</h1>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">ثبت امتحان جدید</h2>
        <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
          <input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="نام امتحان" className="border rounded px-3 py-2" required />
          <select value={form.exam_type} onChange={e=>setForm({...form,exam_type:e.target.value})} className="border rounded px-3 py-2">
            <option value="school">مدرسه</option>
            <option value="external">خارجی</option>
            <option value="mock">آزمایشی</option>
            <option value="diagnostic">سنجشی</option>
          </select>
          <input type="date" value={form.exam_date} onChange={e=>setForm({...form,exam_date:e.target.value})} className="border rounded px-3 py-2" />
          <input value={form.provider} onChange={e=>setForm({...form,provider:e.target.value})} placeholder="موسسه" className="border rounded px-3 py-2" />
          <input type="number" value={form.total_questions} onChange={e=>setForm({...form,total_questions:Number(e.target.value)})} placeholder="تعداد کل" className="border rounded px-3 py-2" />
          <div className="flex gap-2">
            <input type="number" value={form.correct_count} onChange={e=>setForm({...form,correct_count:Number(e.target.value)})} placeholder="درست" className="border rounded px-3 py-2 flex-1" />
            <input type="number" value={form.wrong_count} onChange={e=>setForm({...form,wrong_count:Number(e.target.value)})} placeholder="غلط" className="border rounded px-3 py-2 flex-1" />
            <input type="number" value={form.unanswered_count} onChange={e=>setForm({...form,unanswered_count:Number(e.target.value)})} placeholder="نزده" className="border rounded px-3 py-2 flex-1" />
          </div>
          <button type="submit" className="col-span-2 bg-blue-600 text-white py-2 rounded hover:bg-blue-700">ثبت امتحان - تحلیل جدا از تست‌های عادی</button>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">لیست امتحانات</h2>
        <div className="space-y-3">
          {exams.map(ex=>(
            <div key={ex.id} className="border rounded-lg p-4">
              <div className="flex justify-between">
                <div>
                  <p className="font-bold">{ex.name}</p>
                  <p className="text-sm text-gray-600">{ex.exam_type} - {ex.provider} - {ex.exam_date}</p>
                </div>
                <div className="text-sm">
                  <span className="text-green-600">{ex.correct_count} درست</span>
                  <span className="text-red-600 mx-2">{ex.wrong_count} غلط</span>
                  <span className="text-gray-500">{ex.unanswered_count} نزده</span>
                  {ex.percentage && <span className="mr-2 font-bold">{ex.percentage}%</span>}
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-2">امتحانات در تحلیل جداگانه از تست‌های عادی نگهداری می‌شوند اما به Student State کمک می‌کنند و سوالات غلط به ضعف‌ها اضافه می‌شوند</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
