import { useEffect, useState } from 'react'
import { dashboardAPI } from '../api/client'
import { Link } from 'react-router-dom'

export default function Dashboard() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    dashboardAPI.get().then(res => {
      setData(res.data)
      setLoading(false)
    }).catch(err => {
      setError(err.response?.data?.detail || 'خطا در بارگذاری')
      setLoading(false)
    })
  }, [])

  if (loading) return <div className="p-6">در حال بارگذاری...</div>
  if (error) return <div className="p-6 text-red-600">{error}</div>
  if (!data) return <div className="p-6">داده‌ای یافت نشد</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">داشبورد</h1>
      
      {/* Today's work */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold text-lg mb-4">📅 کارهای امروز</h2>
          <p className="text-3xl font-bold text-blue-600">{data.today?.task_count || 0}</p>
          <p className="text-sm text-gray-500 mt-1">کار برای امروز</p>
          <div className="mt-4 space-y-2">
            {data.today?.tasks?.slice(0,3).map((t: any) => (
              <div key={t.task_id} className="text-sm p-2 bg-gray-50 rounded">
                {t.title}
              </div>
            ))}
          </div>
          <Link to="/today" className="text-blue-600 text-sm mt-3 inline-block hover:underline">مشاهده همه →</Link>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold text-lg mb-4">📊 پیشرفت کلی</h2>
          <div className="space-y-3">
            <div>
              <p className="text-sm text-gray-600">تسلط</p>
              <p className="text-2xl font-bold text-green-600">{data.weekly_progress?.progress?.mastery?.mastery_percent?.toFixed(0) || 0}%</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">دقت</p>
              <p className="text-xl font-bold">{data.weekly_progress?.progress?.accuracy?.accuracy_percent?.toFixed(0) || 0}%</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">پوشش</p>
              <p className="text-xl font-bold">{data.weekly_progress?.progress?.coverage?.coverage_percent?.toFixed(0) || 0}%</p>
            </div>
          </div>
          <Link to="/progress" className="text-blue-600 text-sm mt-3 inline-block hover:underline">جزئیات پیشرفت →</Link>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold text-lg mb-4">🎯 اولویت‌ها</h2>
          <div className="space-y-2">
            {data.student_state?.priorities?.map((p: any, i: number) => (
              <div key={i} className="p-2 bg-yellow-50 rounded text-sm">
                <span className="font-medium">{p.message}</span>
              </div>
            ))}
            {(!data.student_state?.priorities || data.student_state.priorities.length === 0) && (
              <p className="text-sm text-gray-500">مورد خاصی نیست</p>
            )}
          </div>
        </div>
      </div>

      {/* Suggestions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold text-lg mb-4">💡 پیشنهادهای سیستم</h2>
        {data.suggestions?.length > 0 ? (
          <div className="space-y-3">
            {data.suggestions.map((s: any, i: number) => (
              <div key={i} className="border rounded-lg p-4">
                <p className="font-medium">{s.task?.title_fa || s.task?.title}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {s.reasons?.map((r: any, j: number) => (
                    <span key={j} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                      {r.description_fa}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500">پیشنهادی وجود ندارد</p>
        )}
      </div>

      {/* Deadlines */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold text-lg mb-4">📋 تکالیف نزدیک</h2>
          {data.deadlines?.homework?.length > 0 ? (
            <ul className="space-y-2">
              {data.deadlines.homework.map((hw: any) => (
                <li key={hw.id} className="flex justify-between text-sm p-2 bg-gray-50 rounded">
                  <span>{hw.title}</span>
                  <span className="text-gray-500">{hw.due_date}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500 text-sm">تکلیفی وجود ندارد</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold text-lg mb-4">🎓 امتحانات نزدیک</h2>
          {data.deadlines?.exams?.length > 0 ? (
            <ul className="space-y-2">
              {data.deadlines.exams.map((ex: any) => (
                <li key={ex.id} className="flex justify-between text-sm p-2 bg-gray-50 rounded">
                  <span>{ex.name}</span>
                  <span className="text-gray-500">{ex.exam_date}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500 text-sm">امتحانی وجود ندارد</p>
          )}
        </div>
      </div>

      {/* Weakness */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold text-lg mb-4">⚠️ مباحث ضعیف</h2>
        {data.weakest_topics?.length > 0 ? (
          <div className="space-y-2">
            {data.weakest_topics.map((w: any) => (
              <div key={w.book_node_id} className="flex justify-between items-center p-2 bg-red-50 rounded">
                <span className="text-sm">{w.node_title}</span>
                <span className="text-sm font-bold text-red-600">{w.accuracy?.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">مبحث ضعیفی یافت نشد</p>
        )}
      </div>

      {/* Recent activity */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold text-lg mb-4">🕐 فعالیت‌های اخیر</h2>
        {data.recent_activity?.length > 0 ? (
          <div className="space-y-2">
            {data.recent_activity.map((act: any) => (
              <div key={act.id} className="flex justify-between items-center p-3 border rounded-lg">
                <div>
                  <p className="font-medium text-sm">{act.title}</p>
                  <p className="text-xs text-gray-500">{act.test_type} - {act.finished_at ? new Date(act.finished_at).toLocaleDateString('fa-IR') : ''}</p>
                </div>
                <div className="text-sm">
                  <span className="text-green-600">{act.correct}✓</span>
                  <span className="text-red-600 mr-2">{act.wrong}✗</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">فعالیتی ثبت نشده</p>
        )}
      </div>
    </div>
  )
}
