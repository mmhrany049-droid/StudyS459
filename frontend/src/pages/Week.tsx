import { useEffect, useState } from 'react'
import { plannerAPI, goalsAPI } from '../api/client'
import { getSaturdayOfWeek, getPersianDayName } from '../utils'

export default function Week() {
  const [weekStart, setWeekStart] = useState(getSaturdayOfWeek())
  const [weekData, setWeekData] = useState<any>(null)
  const [suggestions, setSuggestions] = useState<any>(null)
  const [catchup, setCatchup] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [goals, setGoals] = useState<any[]>([])

  const loadData = () => {
    setLoading(true)
    Promise.all([
      plannerAPI.getWeek(weekStart),
      plannerAPI.suggestions(weekStart),
      plannerAPI.catchup(weekStart),
      goalsAPI.list()
    ]).then(([weekRes, sugRes, catchRes, goalsRes]) => {
      setWeekData(weekRes.data)
      setSuggestions(sugRes.data)
      setCatchup(catchRes.data)
      setGoals(goalsRes.data)
      setLoading(false)
    }).catch(err => {
      console.error(err)
      setLoading(false)
    })
  }

  useEffect(() => {
    loadData()
  }, [weekStart])

  if (loading) return <div>در حال بارگذاری...</div>

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">برنامه هفته</h1>
        <input
          type="date"
          value={weekStart}
          onChange={e => setWeekStart(e.target.value)}
          className="border rounded-lg px-3 py-2"
        />
      </div>

      {/* Goals */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">اهداف هفته</h2>
        {goals.length > 0 ? (
          <div className="space-y-2">
            {goals.filter(g => g.week_start_date === weekStart).map(goal => (
              <div key={goal.id} className="border rounded-lg p-3">
                <p className="font-medium">هدف از {goal.week_start_date} تا {goal.week_end_date}</p>
                <p className="text-sm text-gray-600">تعداد تست هدف: {goal.test_count_goal || 'نامشخص'} - پیشرفت: {goal.progress_percent?.toFixed(0)}%</p>
                <div className="mt-2 space-y-1">
                  {goal.items?.map((item: any) => (
                    <div key={item.id} className="text-sm flex justify-between">
                      <span>{item.book_title} - {item.node_title || 'کل کتاب'}</span>
                      <span>{item.completed_tests}/{item.target_tests}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">هدفی برای این هفته ثبت نشده</p>
        )}
      </div>

      {/* Suggestions */}
      {suggestions && (
        <div className="bg-blue-50 rounded-lg shadow p-6 border border-blue-200">
          <h2 className="font-bold mb-4">💡 پیشنهادهای سیستم</h2>
          {suggestions.suggestions?.length > 0 ? (
            <div className="space-y-3">
              {suggestions.suggestions.map((s: any, i: number) => (
                <div key={i} className="bg-white rounded-lg p-4 border">
                  <p className="font-medium">{s.task?.title_fa || s.task?.title}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {s.reasons?.map((r: any, j: number) => (
                      <span key={j} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
                        {r.description_fa}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">امتیاز: {s.score?.toFixed(1)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600">پیشنهادی وجود ندارد</p>
          )}
          
          {suggestions.capacity_warnings?.length > 0 && (
            <div className="mt-4">
              <h3 className="font-bold text-sm text-red-600 mb-2">⚠️ هشدار ظرفیت</h3>
              {suggestions.capacity_warnings.map((w: any, i: number) => (
                <p key={i} className="text-sm text-red-600">{w.date}: {w.planned_minutes} دقیقه برنامه‌ریزی شده، ظرفیت {w.available_capacity_minutes} دقیقه</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Week grid */}
      <div className="grid grid-cols-7 gap-4">
        {weekData?.days?.map((day: any) => (
          <div key={day.date} className={`bg-white rounded-lg shadow p-3 ${day.is_catchup_day ? 'bg-yellow-50 border-2 border-yellow-200' : ''}`}>
            <div className="text-center mb-3">
              <p className="font-bold text-sm">{getPersianDayName(day.day_of_week)}</p>
              <p className="text-xs text-gray-500">{day.date}</p>
              <p className="text-xs mt-1">
                {day.planned_minutes}/{day.available_capacity_minutes} دقیقه
                {day.is_over_capacity && <span className="text-red-600"> ⚠️</span>}
              </p>
            </div>
            <div className="space-y-2">
              {day.placements?.map((pl: any) => (
                <div key={pl.id} className="bg-white border rounded p-2 text-xs" style={{ borderRightWidth: 3, borderRightColor: pl.task?.priority > 5 ? '#ef4444' : '#3b82f6' }}>
                  <p className="font-medium truncate">{pl.task?.title_fa || pl.task?.title}</p>
                  <p className="text-gray-500">{pl.task?.estimated_duration_minutes}د</p>
                </div>
              ))}
              {day.placements?.length === 0 && (
                <p className="text-xs text-gray-400 text-center">خالی</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Catchup */}
      {catchup && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">🔄 کارهای قابل انتقال به پنجشنبه/جمعه</h2>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h3 className="font-medium text-sm mb-2">پیشنهاد انتقال</h3>
              {catchup.assigned?.map((a: any, i: number) => (
                <div key={i} className="text-sm p-2 border rounded mb-1">
                  {a.task?.title_fa} → {a.suggested_date} ({a.day})
                </div>
              ))}
            </div>
            <div>
              <h3 className="font-medium text-sm mb-2">ظرفیت</h3>
              <p className="text-sm">پنجشنبه: {catchup.thursday_capacity?.remaining} دقیقه باقی‌مانده</p>
              <p className="text-sm">جمعه: {catchup.friday_capacity?.remaining} دقیقه باقی‌مانده</p>
            </div>
          </div>
        </div>
      )}

      {/* Unplaced */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">کارهای بدون تاریخ</h2>
        <div className="space-y-2">
          {weekData?.unplaced_tasks?.map((task: any) => (
            <div key={task.id} className="border rounded-lg p-3 flex justify-between items-center">
              <div>
                <p className="font-medium text-sm">{task.title_fa || task.title}</p>
                <p className="text-xs text-gray-500">{task.reason}</p>
              </div>
              <span className="text-xs bg-gray-100 px-2 py-1 rounded">{task.estimated_duration_minutes} دقیقه</span>
            </div>
          ))}
          {(!weekData?.unplaced_tasks || weekData.unplaced_tasks.length === 0) && (
            <p className="text-sm text-gray-500">همه کارها زمان‌بندی شده‌اند</p>
          )}
        </div>
      </div>
    </div>
  )
}
