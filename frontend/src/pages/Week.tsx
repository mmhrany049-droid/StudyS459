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
  const [draggedPlacement, setDraggedPlacement] = useState<any>(null)

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

  const handleDragStart = (e: React.DragEvent, placement: any) => {
    setDraggedPlacement(placement)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  const handleDrop = async (e: React.DragEvent, targetDate: string) => {
    e.preventDefault()
    if (!draggedPlacement) return
    if (draggedPlacement.date === targetDate) {
      // Reorder within same day - for simplicity, just keep
      setDraggedPlacement(null)
      return
    }
    try {
      // Update placement date via reorder API
      await plannerAPI.reorder({ placements: [{ placement_id: draggedPlacement.id, date: targetDate, order_index: 0 }] })
      loadData()
    } catch (err) {
      console.error(err)
    }
    setDraggedPlacement(null)
  }

  const handleDropUnplaced = async (e: React.DragEvent, taskId: number, targetDate: string) => {
    e.preventDefault()
    try {
      await plannerAPI.createPlacement({ task_id: taskId, date: targetDate, order_index: 0 })
      loadData()
    } catch (err:any) {
      alert(err.response?.data?.detail || 'خطا')
    }
  }

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
          <p className="text-gray-500 text-sm">هدفی برای این هفته ثبت نشده - <a href="/goals" className="text-blue-600 hover:underline">ایجاد هدف</a></p>
        )}
      </div>

      {/* Suggestions */}
      {suggestions && (
        <div className="bg-blue-50 rounded-lg shadow p-6 border border-blue-200">
          <h2 className="font-bold mb-4">💡 پیشنهادهای سیستم (بالای لیست کارهای روزانه)</h2>
          <p className="text-xs text-gray-600 mb-3">پیشنهادها بر اساس: برنامه مدرسه، کلاس خارجی، ساعات شلوغی، ظرفیت، اهداف هفتگی، تکالیف، نیاز مرور، امتحانات، مهلت‌ها، کارهای ناتمام، ضعف‌های اخیر - هر پیشنهاد دلیل ساختاریافته دارد</p>
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
                  <p className="text-xs text-gray-500 mt-2">امتیاز: {s.score?.toFixed(1)} - {s.task?.reason}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-600">پیشنهادی وجود ندارد</p>
          )}
          
          {suggestions.capacity_warnings?.length > 0 && (
            <div className="mt-4">
              <h3 className="font-bold text-sm text-red-600 mb-2">⚠️ هشدار ظرفیت - سیستم هشدار می‌دهد، حذف بی‌صدا نمی‌کند</h3>
              {suggestions.capacity_warnings.map((w: any, i: number) => (
                <p key={i} className="text-sm text-red-600">{w.date}: {w.planned_minutes} دقیقه برنامه‌ریزی شده، ظرفیت {w.available_capacity_minutes} دقیقه - بیش از حد {w.over_by} دقیقه</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Week grid - Task cards rectangular blocks vertically stacked, higher = higher priority */}
      <div className="grid grid-cols-7 gap-4">
        {weekData?.days?.map((day: any) => (
          <div 
            key={day.date} 
            className={`bg-white rounded-lg shadow p-3 min-h-[300px] ${day.is_catchup_day ? 'bg-yellow-50 border-2 border-yellow-200' : ''}`}
            onDragOver={handleDragOver}
            onDrop={(e)=>handleDrop(e, day.date)}
          >
            <div className="text-center mb-3">
              <p className="font-bold text-sm">{getPersianDayName(day.day_of_week)}</p>
              <p className="text-xs text-gray-500">{day.date}</p>
              <p className="text-xs mt-1">
                {day.planned_minutes}/{day.available_capacity_minutes} دقیقه
                {day.is_over_capacity && <span className="text-red-600"> ⚠️ بیش از ظرفیت</span>}
              </p>
              {day.is_catchup_day && <p className="text-xs text-yellow-700 font-bold mt-1">روز جبرانی</p>}
            </div>
            <div className="space-y-2">
              {day.placements?.sort((a:any,b:any)=>a.order_index-b.order_index).map((pl: any) => (
                <div 
                  key={pl.id} 
                  draggable
                  onDragStart={(e)=>handleDragStart(e, pl)}
                  className="bg-white border rounded p-2 text-xs cursor-move shadow-sm hover:shadow-md transition-shadow rectangular-block"
                  style={{ borderRightWidth: 4, borderRightColor: pl.task?.priority > 5 ? '#ef4444' : pl.task?.priority > 2 ? '#f59e0b' : '#3b82f6', minHeight: '60px' }}
                  title={`اولویت ${pl.task?.priority} - بالاتر یعنی اولویت بالاتر`}
                >
                  <p className="font-medium truncate">{pl.task?.title_fa || pl.task?.title}</p>
                  <p className="text-gray-500">{pl.task?.estimated_duration_minutes}د - {pl.task?.task_type}</p>
                  <p className="text-[10px] text-gray-400 truncate">{pl.task?.reason?.slice(0,30)}</p>
                  <div className="flex gap-1 mt-1">
                    <span className="text-[10px] bg-gray-100 px-1 rounded">{pl.task?.source}</span>
                    <span className={`text-[10px] px-1 rounded ${pl.task?.status==='completed'?'bg-green-100 text-green-700':'bg-yellow-100'}`}>{pl.task?.status}</span>
                  </div>
                </div>
              ))}
              {day.placements?.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-8 border-2 border-dashed rounded">خالی - تسک‌ها را اینجا بکشید</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Catchup */}
      {catchup && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">🔄 کارهای قابل انتقال به پنجشنبه/جمعه - اولویت‌بندی واقعی</h2>
          <p className="text-xs text-gray-600 mb-3">کارهای ناتمام شنبه تا چهارشنبه واجد شرایط جبرانی پنجشنبه/جمعه می‌شوند. همه چیز بی‌رویه به روزهای جبرانی ریخته نمی‌شود. اولویت: 1. عقب‌افتاده/حساس به مهلت 2. تکالیف 3. حیاتی برای هدف 4. حیاتی برای مرور 5. سایر کارهای ناتمام</p>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h3 className="font-medium text-sm mb-2">پیشنهاد انتقال</h3>
              {catchup.assigned?.map((a: any, i: number) => (
                <div key={i} className="text-sm p-2 border rounded mb-1">
                  {a.task?.title_fa} → {a.suggested_date} ({a.day})
                </div>
              ))}
              {catchup.unassigned?.length>0 && (
                <div className="mt-3">
                  <h4 className="text-xs font-bold">انتقال داده نشد (ظرفیت ناکافی)</h4>
                  {catchup.unassigned.map((t:any,i:number)=><p key={i} className="text-xs p-1 bg-red-50 rounded mb-1">{t.title_fa}</p>)}
                </div>
              )}
            </div>
            <div>
              <h3 className="font-medium text-sm mb-2">ظرفیت</h3>
              <p className="text-sm">پنجشنبه: کل {catchup.thursday_capacity?.total} - برنامه‌ریزی {catchup.thursday_capacity?.planned} - باقی‌مانده {catchup.thursday_capacity?.remaining}</p>
              <p className="text-sm">جمعه: کل {catchup.friday_capacity?.total} - برنامه‌ریزی {catchup.friday_capacity?.planned} - باقی‌مانده {catchup.friday_capacity?.remaining}</p>
            </div>
          </div>
        </div>
      )}

      {/* Unplaced - draggable */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">کارهای بدون تاریخ - کاندیدهای هفته (کاربر انتخاب می‌کند هر تسک متعلق به کدام روز است)</h2>
        <p className="text-xs text-gray-500 mb-3">سیستم کاندیدها را می‌سازد، کاربر نهایی‌سازی روزانه را انجام می‌دهد. سیستم نباید بی‌صدا جای‌گذاری روزانه را نهایی کند.</p>
        <div className="space-y-2">
          {weekData?.unplaced_tasks?.map((task: any) => (
            <div 
              key={task.id} 
              draggable
              onDragStart={(e)=>{
                e.dataTransfer.setData('taskId', task.id.toString())
              }}
              className="border rounded-lg p-3 flex justify-between items-center cursor-move hover:bg-gray-50 rectangular-block"
              style={{ borderRightWidth: 4, borderRightColor: task.priority > 5 ? '#ef4444' : '#3b82f6' }}
            >
              <div>
                <p className="font-medium text-sm">{task.title_fa || task.title}</p>
                <p className="text-xs text-gray-500">{task.reason} - منبع: {task.source} - {task.task_type}</p>
                <div className="flex gap-1 mt-1">
                  {task.reason_structured && (()=>{ try{ const rs=JSON.parse(task.reason_structured); return rs.map((r:any,i:number)=><span key={i} className="text-[10px] bg-blue-50 text-blue-600 px-1 rounded">{r.description_fa}</span>) }catch{return null} })()}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs bg-gray-100 px-2 py-1 rounded">{task.estimated_duration_minutes} دقیقه</span>
                <span className="text-xs">اولویت {task.priority}</span>
              </div>
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
