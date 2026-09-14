import { useEffect, useState } from 'react'
import { analyticsAPI } from '../api/client'

export default function Analytics() {
  const [overview, setOverview] = useState<any>(null)
  const [weakest, setWeakest] = useState<any[]>([])
  const [mistakes, setMistakes] = useState<any[]>([])

  useEffect(()=>{
    analyticsAPI.overview().then(res=>setOverview(res.data))
    analyticsAPI.weakest().then(res=>setWeakest(res.data))
    analyticsAPI.recentMistakes().then(res=>setMistakes(res.data))
  },[])

  if(!overview) return <div>در حال بارگذاری...</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">تحلیل عمیق</h1>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">تفکیک دقیق معیارها</h2>
        <div className="grid grid-cols-4 gap-4 text-center">
          <div className="p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-600">Volume - حجم فعالیت</p>
            <p className="text-2xl font-bold">{overview.volume.total_tests} تست</p>
            <p className="text-sm">{overview.volume.total_questions} سوال</p>
            <p className="text-xs text-gray-500 mt-2">چقدر فعالیت انجام شده</p>
          </div>
          <div className="p-4 bg-green-50 rounded-lg">
            <p className="text-sm text-gray-600">Coverage - پوشش</p>
            <p className="text-2xl font-bold">{overview.coverage.coverage_percent.toFixed(0)}%</p>
            <p className="text-sm">{overview.coverage.attempted_questions} از {overview.coverage.total_questions_in_pool}</p>
            <p className="text-xs text-gray-500 mt-2">چقدر از بانک دیده شده</p>
          </div>
          <div className="p-4 bg-yellow-50 rounded-lg">
            <p className="text-sm text-gray-600">Accuracy - دقت</p>
            <p className="text-2xl font-bold">{overview.accuracy.accuracy_percent.toFixed(0)}%</p>
            <p className="text-sm">{overview.accuracy.correct} درست از {overview.accuracy.answered_total}</p>
            <p className="text-xs text-gray-500 mt-2">درستی در پاسخ‌های داده شده</p>
          </div>
          <div className="p-4 bg-purple-50 rounded-lg">
            <p className="text-sm text-gray-600">Mastery - تسلط</p>
            <p className="text-2xl font-bold text-purple-600">{overview.mastery.mastery_percent.toFixed(0)}%</p>
            <p className="text-sm">{overview.mastery.estimated_level}</p>
            <p className="text-xs text-gray-500 mt-2">برآورد فهم = دقت × پوشش</p>
          </div>
        </div>
        <div className="mt-4 p-3 bg-yellow-50 rounded text-sm">
          <p>⚠️ مثال مستندات: کاربری ممکن است 25% پوشش و 72% دقت داشته باشد، این به معنای 72% تسلط کل کتاب نیست. تسلط با فرمول قابل تنظیم محاسبه می‌شود و پوشش را در نظر می‌گیرد.</p>
          <p className="mt-1">فرمول فعلی: {overview.mastery.calculation_method}</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">روند زمانی</h2>
        <div className="grid grid-cols-7 gap-2">
          {overview.trends?.map((t:any)=>(
            <div key={t.date} className="text-center p-2 border rounded">
              <p className="text-xs">{t.date}</p>
              <p className="font-bold text-sm">{t.attempts}</p>
              <p className="text-xs">{t.accuracy.toFixed(0)}%</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">ضعیف‌ترین مباحث</h2>
          <div className="space-y-2">
            {weakest.map((w:any)=>(
              <div key={w.book_node_id} className="flex justify-between text-sm p-2 bg-red-50 rounded">
                <span>{w.node_title}</span>
                <span className="font-bold text-red-600">{w.accuracy.toFixed(0)}% - {w.wrong_count} غلط</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">اشتباهات اخیر</h2>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {mistakes.map((m:any)=>(
              <div key={m.attempt_id} className="text-sm p-2 border rounded">
                <p className="truncate">{m.question_text?.slice(0,80)}</p>
                <p className="text-xs text-gray-500">{m.question_stable_id} - {new Date(m.created_at).toLocaleDateString('fa-IR')}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">قابلیت بازسازی تحلیل از داده خام</h2>
        <p className="text-sm text-gray-600">تمام تحلیل‌ها از جدول question_attempts بازسازی می‌شوند. داده خام شامل user, question, session, answer, result, timestamp, duration, context است و هرگز بازنویسی نمی‌شود. Analytics نباید تنها منبع حقیقت باشد.</p>
      </div>
    </div>
  )
}
