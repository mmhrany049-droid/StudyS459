import { useEffect, useState } from 'react'
import { plannerAPI } from '../api/client'
import { getSaturdayOfWeek } from '../utils'

export default function Today() {
  const [weekData, setWeekData] = useState<any>(null)
  const [todayStr, setTodayStr] = useState(new Date().toISOString().split('T')[0])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const saturday = getSaturdayOfWeek()
    plannerAPI.getWeek(saturday).then(res => {
      setWeekData(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div>در حال بارگذاری...</div>

  const todayDay = weekData?.days?.find((d: any) => d.date === todayStr)

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">امروز - {todayStr}</h1>
      
      {todayDay ? (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between mb-4">
            <h2 className="font-bold">کارهای امروز - {todayDay.day_of_week}</h2>
            <div className="text-sm">
              <span>ظرفیت: {todayDay.available_capacity_minutes} دقیقه</span>
              <span className="mx-2">|</span>
              <span>برنامه‌ریزی شده: {todayDay.planned_minutes} دقیقه</span>
              {todayDay.is_over_capacity && <span className="text-red-600 mr-2">⚠️ بیش از ظرفیت</span>}
            </div>
          </div>
          
          {todayDay.placements?.length > 0 ? (
            <div className="space-y-3">
              {todayDay.placements.map((pl: any) => (
                <div key={pl.id} className="border rounded-lg p-4 flex justify-between items-center" style={{ borderRightWidth: 4, borderRightColor: pl.task?.priority > 5 ? '#ef4444' : '#3b82f6' }}>
                  <div>
                    <p className="font-medium">{pl.task?.title_fa || pl.task?.title}</p>
                    <p className="text-sm text-gray-500">{pl.task?.reason} - {pl.task?.estimated_duration_minutes} دقیقه</p>
                  </div>
                  <div className="flex gap-2">
                    <span className={`text-xs px-2 py-1 rounded ${pl.task?.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                      {pl.task?.status}
                    </span>
                    <span className="text-xs bg-gray-100 px-2 py-1 rounded">اولویت {pl.task?.priority}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">کاری برای امروز برنامه‌ریزی نشده</p>
          )}
        </div>
      ) : (
        <p>داده‌ای برای امروز یافت نشد</p>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">کارهای بدون تاریخ</h2>
        {weekData?.unplaced_tasks?.length > 0 ? (
          <div className="space-y-2">
            {weekData.unplaced_tasks.map((task: any) => (
              <div key={task.id} className="p-3 border rounded-lg flex justify-between">
                <span>{task.title_fa || task.title}</span>
                <span className="text-sm text-gray-500">{task.estimated_duration_minutes} دقیقه</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">همه کارها زمان‌بندی شده‌اند</p>
        )}
      </div>
    </div>
  )
}
