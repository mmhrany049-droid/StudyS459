import { useEffect, useState } from 'react'
import apiClient from '../api/client'

export default function Review() {
  const [queue, setQueue] = useState<any[]>([])
  const [due, setDue] = useState<any[]>([])

  const load = () => {
    apiClient.get('/review/').then(res=>setQueue(res.data))
    apiClient.get('/review/due').then(res=>setDue(res.data))
  }
  useEffect(()=>{ load() },[])

  const handleUpdate = async (id:number, status:string)=>{
    await apiClient.post(`/review/${id}/update`, null, { params: { status } })
    load()
  }

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">مرور و جبران</h1>
      
      <div className="bg-blue-50 p-4 rounded-lg text-sm">
        <p>سوالات غلط و نزده وارد صف مرور می‌شوند. معماری مرور قابل توسعه است چون الگوریتم دقیق تکرار فاصله‌دار نهایی نشده و نباید به صورت پیچیده و غیرقابل برگشت سخت‌کد شود.</p>
        <p className="mt-2">استراتژی فعلی: simple - بازه‌ها: 1,3,7,14,30 روز - قابل تنظیم via env</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">مرورهای امروز ({due.length})</h2>
          <div className="space-y-2">
            {due.map((item:any)=>(
              <div key={item.id} className="p-3 border rounded flex justify-between">
                <div>
                  <p className="text-sm font-medium">سوال {item.question_id} - کتاب {item.book_id}</p>
                  <p className="text-xs text-gray-500">{item.reason} - {item.next_review_date}</p>
                </div>
                <button onClick={()=>handleUpdate(item.id,'reviewed')} className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">مرور شد</button>
              </div>
            ))}
            {due.length===0 && <p className="text-sm text-gray-500">موردی برای امروز نیست</p>}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">کل صف مرور ({queue.length})</h2>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {queue.map(item=>(
              <div key={item.id} className="p-3 border rounded">
                <div className="flex justify-between">
                  <p className="text-sm font-medium">{item.stable_id} - {item.question_text?.slice(0,50)}</p>
                  <span className="text-xs bg-yellow-100 px-2 py-1 rounded">{item.reason}</span>
                </div>
                <p className="text-xs text-gray-500 mt-1">تکرار: {item.repetition_count} - فاصله: {item.interval_days} روز - بعدی: {item.next_review_date}</p>
                <div className="flex gap-2 mt-2">
                  <button onClick={()=>handleUpdate(item.id,'reviewed')} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">مرور شد</button>
                  <button onClick={()=>handleUpdate(item.id,'mastered')} className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">مسلط شدم</button>
                  <button onClick={()=>handleUpdate(item.id,'postponed')} className="text-xs bg-gray-100 px-2 py-1 rounded">تعویق</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
