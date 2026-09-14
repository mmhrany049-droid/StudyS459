import { useEffect, useState } from 'react'
import { authAPI } from '../api/client'

export default function Settings() {
  const [user, setUser] = useState<any>(null)

  useEffect(()=>{
    authAPI.me().then(res=>setUser(res.data))
  },[])

  return (
    <div className="space-y-6 max-w-2xl" dir="rtl">
      <h1 className="text-2xl font-bold">تنظیمات</h1>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">پروفایل کاربری</h2>
        {user ? (
          <div className="space-y-2 text-sm">
            <p><span className="font-medium">نام کاربری:</span> {user.username}</p>
            <p><span className="font-medium">ایمیل:</span> {user.email}</p>
            <p><span className="font-medium">نام کامل:</span> {user.full_name || 'تنظیم نشده'}</p>
            <p><span className="font-medium">تاریخ عضویت:</span> {new Date(user.created_at).toLocaleDateString('fa-IR')}</p>
          </div>
        ) : (
          <p>در حال بارگذاری...</p>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">تنظیمات قابل پیکربندی (Open Decisions)</h2>
        <p className="text-sm text-gray-600 mb-4">این موارد به عنوان تصمیمات باز در مستندات مشخص شده‌اند و از طریق متغیرهای محیطی یا سرویس‌های قابل تنظیم مدیریت می‌شوند:</p>
        <ul className="text-sm space-y-2 list-disc list-inside">
          <li>فرمول نمره‌دهی: <code>SCORING_FORMULA</code> - standard, negative_marking</li>
          <li>فرمول تسلط: <code>MASTERY_CORRECT_WEIGHT</code>, <code>MASTERY_WRONG_PENALTY</code>, <code>MASTERY_MIN_ATTEMPTS_FOR_MASTERY</code></li>
          <li>الگوریتم مرور فاصله‌دار: <code>SPACED_REPETITION_STRATEGY</code> - simple, sm2, configurable</li>
          <li>حذف سوالات اخیر: <code>RECENT_QUESTION_EXCLUSION_DAYS</code></li>
          <li>الگوریتم جای‌گذاری زمانی: ظرفیت بر اساس برنامه مدرسه/کلاس محاسبه می‌شود</li>
          <li>مدل نمره‌دهی امتحان: درصد، نمره</li>
          <li>نقش‌های گروه: member, admin, owner - قابل تنظیم</li>
          <li>زمان‌بندی تلگرام: <code>TELEGRAM_REPORT_TIMES</code> - 08:00,20:00</li>
          <li>فرمت وارد کردن: JSON انعطاف‌پذیر با stable_id</li>
          <li>استراتژی احراز هویت: JWT با انقضای قابل تنظیم</li>
          <li>تأثیر امتحان بر تسلط: <code>EXAM_INFLUENCE_ON_MASTERY</code></li>
          <li>وزن‌دهی دشواری: <code>DIFFICULTY_WEIGHTS</code> - 1:1.0,2:1.2,3:1.5</li>
        </ul>
        <p className="text-xs text-gray-500 mt-4">مقادیر پیش‌فرض منطقی برای اجرای سیستم انتخاب شده‌اند و در <code>.env.example</code> مستند شده‌اند.</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">منطقه زمانی</h2>
        <p className="text-sm">منطقه زمانی پیش‌فرض: Asia/Tehran</p>
        <p className="text-xs text-gray-500 mt-2">تمام timestampها به صورت UTC ذخیره می‌شوند و محاسبات هفته/روز با آگاهی از timezone انجام می‌شود. استراتژی متمرکز در config/settings.py</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">امنیت</h2>
        <ul className="text-sm space-y-1 list-disc list-inside">
          <li>احراز هویت JWT با bcrypt</li>
          <li>بررسی مالکیت در تمام endpointهای کاربر-محور</li>
          <li>عدم اعتماد به user_id ارسالی از کلاینت</li>
          <li>مرزهای حریم خصوصی و بررسی دسترسی گروه</li>
          <li>امنیت تلگرام با کد تایید</li>
          <li>عدم نشت داده بین کاربران</li>
        </ul>
      </div>
    </div>
  )
}
