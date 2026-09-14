import { useEffect, useState } from 'react'
import { goalsAPI, booksAPI } from '../api/client'
import { getSaturdayOfWeek } from '../utils'

export default function Goals() {
  const [goals, setGoals] = useState<any[]>([])
  const [books, setBooks] = useState<any[]>([])
  const [nodes, setNodes] = useState<any[]>([])
  const [form, setForm] = useState({
    week_start_date: getSaturdayOfWeek(),
    week_end_date: '',
    test_count_goal: 5,
    items: [] as any[]
  })
  const [itemForm, setItemForm] = useState({ book_id: '', book_node_id: '', target_tests: 1, priority: 0 })

  const load = () => {
    goalsAPI.list().then(res=>setGoals(res.data))
    booksAPI.listBooks().then(res=>setBooks(res.data))
  }
  useEffect(()=>{ load() },[])

  useEffect(()=>{
    // calc week end
    const start = new Date(form.week_start_date)
    const end = new Date(start)
    end.setDate(start.getDate()+6)
    setForm(f=>({...f, week_end_date: end.toISOString().split('T')[0]}))
  },[form.week_start_date])

  useEffect(()=>{
    if(itemForm.book_id){
      booksAPI.getNodes(Number(itemForm.book_id)).then(res=>{
        const flat:any[]=[]
        const trav=(arr:any[])=>{ arr.forEach(n=>{ flat.push(n); if(n.children) trav(n.children) }) }
        trav(res.data)
        setNodes(flat)
      })
    }
  },[itemForm.book_id])

  const addItem = ()=>{
    if(!itemForm.book_id) return
    setForm({...form, items: [...form.items, {
      book_id: Number(itemForm.book_id),
      book_node_id: itemForm.book_node_id ? Number(itemForm.book_node_id) : undefined,
      target_tests: Number(itemForm.target_tests),
      priority: Number(itemForm.priority)
    }]})
    setItemForm({ book_id: '', book_node_id: '', target_tests: 1, priority: 0 })
  }

  const handleCreate = async (e:React.FormEvent)=>{
    e.preventDefault()
    try{
      const payload = {
        week_start_date: form.week_start_date,
        week_end_date: form.week_end_date,
        test_count_goal: form.test_count_goal || undefined,
        items: form.items
      }
      await goalsAPI.create(payload)
      setForm({ week_start_date: getSaturdayOfWeek(), week_end_date: '', test_count_goal: 5, items: [] })
      load()
    }catch(err:any){ alert(err.response?.data?.detail || 'خطا') }
  }

  const handleGenerateTasks = async (id:number)=>{
    await goalsAPI.generateTasks(id)
    alert('تسک‌های کاندید ساخته شد')
  }

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">اهداف هفتگی</h1>
      
      <div className="bg-blue-50 p-4 rounded-lg text-sm">
        <p className="font-bold">دو نوع هدف مستقل:</p>
        <p>A. تعداد تست‌ها - B. مباحث</p>
        <p>یک هفته ممکن است فقط هدف تعدادی، فقط موضوعی، یا هر دو داشته باشد.</p>
        <p className="mt-2 font-bold">قانون اولویت: اگر هر دو وجود دارد، اهداف موضوعی انتخاب موضوع را هدایت می‌کند، هدف تعدادی حجم کلی را کنترل می‌کند. یک تسک ممکن است هر دو را ارضا کند. پیشرفت نباید به اشتباه دوبار شمرده شود.</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">ایجاد هدف هفتگی جدید</h2>
        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-sm">شروع هفته (شنبه)</label>
              <input type="date" value={form.week_start_date} onChange={e=>setForm({...form, week_start_date: e.target.value})} className="border rounded px-3 py-2 w-full" required />
            </div>
            <div>
              <label className="text-sm">پایان هفته (جمعه)</label>
              <input type="date" value={form.week_end_date} readOnly className="border rounded px-3 py-2 w-full bg-gray-100" />
            </div>
            <div>
              <label className="text-sm">هدف تعداد تست (اختیاری)</label>
              <input type="number" value={form.test_count_goal} onChange={e=>setForm({...form, test_count_goal: Number(e.target.value)})} className="border rounded px-3 py-2 w-full" />
            </div>
          </div>

          <div className="border rounded-lg p-4 bg-gray-50">
            <h3 className="font-medium mb-2">افزودن مبحث هدف</h3>
            <div className="grid grid-cols-4 gap-2">
              <select value={itemForm.book_id} onChange={e=>setItemForm({...itemForm, book_id: e.target.value})} className="border rounded px-2 py-1">
                <option value="">کتاب</option>
                {books.map(b=> <option key={b.id} value={b.id}>{b.title_fa || b.title}</option>)}
              </select>
              <select value={itemForm.book_node_id} onChange={e=>setItemForm({...itemForm, book_node_id: e.target.value})} className="border rounded px-2 py-1">
                <option value="">مبحث (اختیاری)</option>
                {nodes.map(n=> <option key={n.id} value={n.id}>{n.title_fa || n.title}</option>)}
              </select>
              <input type="number" value={itemForm.target_tests as any} onChange={e=>setItemForm({...itemForm, target_tests: Number(e.target.value) as any})} placeholder="تعداد هدف" className="border rounded px-2 py-1" />
              <button type="button" onClick={addItem} className="bg-blue-100 text-blue-700 rounded px-2 py-1 text-sm">افزودن</button>
            </div>
            <div className="mt-2 space-y-1">
              {form.items.map((it,i)=>(
                <div key={i} className="text-xs flex justify-between bg-white p-2 rounded border">
                  <span>کتاب {it.book_id} - مبحث {it.book_node_id || 'کل'} - {it.target_tests} تست - اولویت {it.priority}</span>
                  <button type="button" onClick={()=>setForm({...form, items: form.items.filter((_,idx)=>idx!==i)})} className="text-red-600">حذف</button>
                </div>
              ))}
            </div>
          </div>

          <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">ایجاد هدف</button>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">لیست اهداف</h2>
        <div className="space-y-3">
          {goals.map(g=>(
            <div key={g.id} className="border rounded-lg p-4">
              <div className="flex justify-between">
                <div>
                  <p className="font-bold">{g.week_start_date} تا {g.week_end_date}</p>
                  <p className="text-sm text-gray-600">تعداد هدف: {g.test_count_goal || 'ندارد'} - موضوعی: {g.topic_goal_enabled ? 'بله' : 'خیر'} - پیشرفت: {g.progress_percent?.toFixed(0)}%</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={()=>handleGenerateTasks(g.id)} className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded">ساخت تسک‌های کاندید</button>
                </div>
              </div>
              <div className="mt-2 space-y-1">
                {g.items?.map((it:any)=>(
                  <div key={it.id} className="text-xs flex justify-between bg-gray-50 p-2 rounded">
                    <span>{it.book_title} - {it.node_title || 'کل کتاب'}</span>
                    <span>{it.completed_tests}/{it.target_tests}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
