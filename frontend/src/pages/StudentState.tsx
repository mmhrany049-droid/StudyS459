import { useEffect, useState } from 'react'
import apiClient from '../api/client'

export default function StudentState() {
  const [state, setState] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(()=>{
    apiClient.get('/student-state/').then(res=>{ setState(res.data); setLoading(false) }).catch(()=>{
      // Try dashboard student_state
      apiClient.get('/dashboard/').then(res=>{ setState(res.data.student_state); setLoading(false) }).catch(()=>setLoading(false))
    })
  },[])

  if(loading) return <div>در حال بارگذاری...</div>

  // If direct endpoint not exist, use dashboard data structure
  if(!state) return <div className="p-6">داده‌ای یافت نشد - از داشبورد استفاده کنید</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">وضعیت یکپارچه دانش‌آموز</h1>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-2">حلقه بازخورد اصلی</h2>
        <p className="text-sm bg-gray-50 p-3 rounded font-mono">Weekly Goal → Candidate Task → Daily Placement → Test Session → Attempts → Analytics → Weakness / Review → Student State → New Recommendations</p>
        <p className="text-xs text-gray-500 mt-2">معماری باید این حلقه را حفظ کند</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">تسلط کلی</p>
          <p className="text-2xl font-bold">{state.analytics_summary?.overall_mastery?.toFixed(0) || 0}%</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">دقت کلی</p>
          <p className="text-2xl font-bold">{state.analytics_summary?.overall_accuracy?.toFixed(0) || 0}%</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">پوشش کلی</p>
          <p className="text-2xl font-bold">{state.analytics_summary?.overall_coverage?.toFixed(0) || 0}%</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">ورودی‌ها</h2>
        <div className="grid grid-cols-4 gap-3 text-sm">
          <div className="p-3 bg-blue-50 rounded"><p>مرورهای در انتظار</p><p className="font-bold text-xl">{state.counts?.review_pending || 0}</p></div>
          <div className="p-3 bg-yellow-50 rounded"><p>مرورهای امروز</p><p className="font-bold text-xl">{state.counts?.review_due || 0}</p></div>
          <div className="p-3 bg-green-50 rounded"><p>تکالیف</p><p className="font-bold text-xl">{state.counts?.homework_pending || 0}</p></div>
          <div className="p-3 bg-red-50 rounded"><p>تکالیف عقب‌افتاده</p><p className="font-bold text-xl">{state.counts?.homework_overdue || 0}</p></div>
          <div className="p-3 bg-purple-50 rounded"><p>امتحانات نزدیک</p><p className="font-bold text-xl">{state.counts?.upcoming_exams || 0}</p></div>
          <div className="p-3 bg-gray-50 rounded"><p>کارهای ناتمام</p><p className="font-bold text-xl">{state.counts?.unfinished_tasks || 0}</p></div>
          <div className="p-3 bg-indigo-50 rounded"><p>برنامه‌ها</p><p className="font-bold text-xl">{state.counts?.schedules || 0}</p></div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">اولویت‌ها (خروجی)</h2>
        <div className="space-y-2">
          {state.priorities?.map((p:any,i:number)=>(
            <div key={i} className="p-3 border rounded flex justify-between">
              <span>{p.message} - {p.message_en}</span>
              <span className={`text-xs px-2 py-1 rounded ${p.level==='high'?'bg-red-100 text-red-700':'bg-yellow-100 text-yellow-700'}`}>{p.level}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">پیشنهادهای جدید</h2>
        <div className="space-y-2">
          {state.suggestions?.map((s:any,i:number)=>(
            <div key={i} className="p-3 border rounded">
              <p className="font-medium text-sm">{s.task?.title_fa || s.task?.title}</p>
              <div className="flex flex-wrap gap-1 mt-1">
                {s.reasons?.map((r:any,j:number)=><span key={j} className="text-xs bg-blue-100 px-2 py-1 rounded">{r.description_fa}</span>)}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">تغییرات وضعیت</h2>
        {state.state_changes?.length>0 ? state.state_changes.map((sc:any,i:number)=>(
          <div key={i} className="p-2 bg-green-50 rounded text-sm">{sc.message}</div>
        )) : <p className="text-sm text-gray-500">تغییر خاصی نیست</p>}
      </div>
    </div>
  )
}
