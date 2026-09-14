import { useEffect, useState } from 'react'
import { analyticsAPI } from '../api/client'

export default function Progress() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    analyticsAPI.progress().then(res => {
      setData(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div>در حال بارگذاری...</div>
  if (!data) return <div>داده‌ای یافت نشد</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">پیشرفت و تحلیل</h1>
      
      {/* Overall */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">حجم فعالیت</p>
          <p className="text-xl font-bold">{data.overall?.volume?.total_tests} تست</p>
          <p className="text-sm">{data.overall?.volume?.total_questions} سوال</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">پوشش</p>
          <p className="text-xl font-bold">{data.overall?.coverage?.coverage_percent?.toFixed(0)}%</p>
          <p className="text-sm">{data.overall?.coverage?.attempted_questions} از {data.overall?.coverage?.total_questions_in_pool}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">دقت</p>
          <p className="text-xl font-bold">{data.overall?.accuracy?.accuracy_percent?.toFixed(0)}%</p>
          <p className="text-sm">{data.overall?.accuracy?.correct} درست از {data.overall?.accuracy?.answered_total}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-500">تسلط</p>
          <p className="text-xl font-bold text-green-600">{data.overall?.mastery?.mastery_percent?.toFixed(0)}%</p>
          <p className="text-sm">{data.overall?.mastery?.estimated_level}</p>
        </div>
      </div>

      <div className="bg-yellow-50 p-4 rounded-lg text-sm">
        <p className="font-bold">تفکیک مفاهیم:</p>
        <p>حجم: چقدر فعالیت انجام شده | پوشش: چقدر از بانک سوال دیده شده | دقت: درستی در بین پاسخ‌های داده شده | تسلط: برآورد فهم = دقت × پوشش</p>
        <p className="mt-1">مثال: 25% پوشش و 72% دقت به معنای 72% تسلط کل کتاب نیست</p>
      </div>

      {/* Trends */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">روند 7 روز اخیر</h2>
        <div className="flex gap-2">
          {data.overall?.trends?.map((t: any) => (
            <div key={t.date} className="flex-1 text-center">
              <p className="text-xs text-gray-500">{t.date}</p>
              <p className="text-sm font-bold">{t.attempts} سوال</p>
              <p className="text-xs">{t.accuracy?.toFixed(0)}% دقت</p>
            </div>
          ))}
        </div>
      </div>

      {/* By subject */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">بر اساس درس</h2>
        <div className="space-y-2">
          {data.by_subject?.map((s: any) => (
            <div key={s.subject_id} className="flex justify-between p-3 border rounded-lg">
              <span>{s.subject_name}</span>
              <div className="flex gap-4 text-sm">
                <span>{s.total_questions} سوال</span>
                <span>{s.accuracy?.toFixed(0)}% دقت</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* By book */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">بر اساس کتاب</h2>
        <div className="space-y-4">
          {data.by_book?.map((b: any) => (
            <div key={b.book_id} className="border rounded-lg p-4">
              <div className="flex justify-between mb-2">
                <span className="font-bold">{b.book_title}</span>
                <span className="text-sm">تسلط {b.mastery?.mastery_percent?.toFixed(0)}%</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <span>حجم: {b.volume?.total_questions}</span>
                <span>پوشش: {b.coverage?.coverage_percent?.toFixed(0)}%</span>
                <span>دقت: {b.accuracy?.accuracy_percent?.toFixed(0)}%</span>
              </div>
              {b.topics?.length > 0 && (
                <details className="mt-2">
                  <summary className="text-sm cursor-pointer">جزئیات مباحث ({b.topics.length})</summary>
                  <div className="mt-2 space-y-1">
                    {b.topics.slice(0,10).map((t: any) => (
                      <div key={t.book_node_id} className="flex justify-between text-xs p-1 bg-gray-50 rounded">
                        <span>{t.node_title}</span>
                        <span>تسلط {t.mastery?.mastery_percent?.toFixed(0)}% | دقت {t.accuracy?.accuracy_percent?.toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Weakest */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">ضعیف‌ترین مباحث</h2>
        {data.weakest_topics?.length > 0 ? (
          <div className="space-y-2">
            {data.weakest_topics.map((w: any) => (
              <div key={w.book_node_id} className="flex justify-between p-3 bg-red-50 rounded-lg">
                <span className="text-sm">{w.node_title}</span>
                <div className="flex gap-3 text-sm">
                  <span>{w.total_attempts} تلاش</span>
                  <span className="font-bold text-red-600">{w.accuracy?.toFixed(0)}%</span>
                  <span className="text-gray-500">{w.last_attempted}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">مبحث ضعیفی یافت نشد</p>
        )}
      </div>

      {/* Recent mistakes */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">اشتباهات اخیر</h2>
        {data.recent_mistakes?.length > 0 ? (
          <div className="space-y-2">
            {data.recent_mistakes.slice(0,10).map((m: any) => (
              <div key={m.attempt_id} className="text-sm p-2 border rounded">
                <p>{m.question_text?.slice(0,100)}...</p>
                <p className="text-xs text-gray-500">{m.created_at} - {m.question_stable_id}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">اشتباه اخیری وجود ندارد</p>
        )}
      </div>

      {/* Unseen */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">سوالات دیده نشده</h2>
        <p>کل: {data.unseen_questions_summary?.total_questions} | دیده شده: {data.unseen_questions_summary?.attempted} | ندیده: {data.unseen_questions_summary?.unseen} | پوشش {data.unseen_questions_summary?.coverage_percent?.toFixed(0)}%</p>
      </div>
    </div>
  )
}
