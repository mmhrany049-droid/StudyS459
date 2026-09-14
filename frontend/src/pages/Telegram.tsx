import { useEffect, useState } from 'react'
import { telegramAPI } from '../api/client'

export default function Telegram() {
  const [conn, setConn] = useState<any>(null)
  const [code, setCode] = useState('')
  const [preview, setPreview] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    telegramAPI.getConnection().then(res=>{ setConn(res.data); setLoading(false) }).catch(()=>setLoading(false))
  }
  useEffect(()=>{ load() },[])

  const handleVerify = async (e: React.FormEvent)=>{
    e.preventDefault()
    try{
      await telegramAPI.verify(code)
      load()
    }catch(err:any){ alert(err.response?.data?.detail || 'خطا') }
  }

  const handlePreview = async (type: string)=>{
    const res = await telegramAPI.preview(type)
    setPreview(res.data)
  }

  const handleSend = async (type: string)=>{
    try{
      await telegramAPI.send(type)
      alert('ارسال شد')
    }catch(err:any){ alert(err.response?.data?.detail || 'خطا - توکن تلگرام تنظیم نشده؟') }
  }

  if(loading) return <div>در حال بارگذاری...</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">اتصال تلگرام</h1>
      
      <div className="bg-blue-50 p-4 rounded-lg text-sm">
        <p className="font-bold">تلگرام به عنوان لایه گزارش‌دهی و یکپارچه‌سازی</p>
        <p>تلگرام منطق کسب‌وکار اصلی را تکثیر نمی‌کند و از همان سرویس‌های اصلی برنامه استفاده می‌کند</p>
        <p>زمان‌بندی گزارش‌ها قابل تنظیم است چون تصمیم نهایی باز است</p>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">وضعیت اتصال</h2>
        {conn ? (
          <div className="space-y-2 text-sm">
            <p>شناسه تلگرام: {conn.telegram_user_id || 'تنظیم نشده'}</p>
            <p>نام کاربری: {conn.telegram_username || 'تنظیم نشده'}</p>
            <p>چت ID: {conn.chat_id || 'تنظیم نشده'}</p>
            <p>تایید شده: {conn.is_verified ? '✅ بله' : '❌ خیر'}</p>
            <p>کد تایید: <span className="font-mono bg-gray-100 px-2 py-1 rounded">{conn.verification_code}</span></p>
          </div>
        ) : (
          <p>اتصالی وجود ندارد</p>
        )}

        {!conn?.is_verified && (
          <form onSubmit={handleVerify} className="mt-4 flex gap-2">
            <input value={code} onChange={e=>setCode(e.target.value)} placeholder="کد تایید" className="border rounded px-3 py-2 flex-1" />
            <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">تایید</button>
          </form>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">تنظیمات گزارش‌ها</h2>
        {conn && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={conn.morning_report_enabled} onChange={e=> telegramAPI.updatePrefs({morning_report_enabled: e.target.checked}).then(load)} />
              گزارش صبح
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={conn.evening_report_enabled} onChange={e=> telegramAPI.updatePrefs({evening_report_enabled: e.target.checked}).then(load)} />
              گزارش شب
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={conn.homework_reminder_enabled} onChange={e=> telegramAPI.updatePrefs({homework_reminder_enabled: e.target.checked}).then(load)} />
              یادآور تکالیف
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={conn.review_reminder_enabled} onChange={e=> telegramAPI.updatePrefs({review_reminder_enabled: e.target.checked}).then(load)} />
              یادآور مرور
            </label>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">پیش‌نمایش گزارش‌ها</h2>
        <div className="flex gap-2 mb-4">
          <button onClick={()=>handlePreview('morning')} className="bg-blue-100 text-blue-700 px-3 py-1 rounded text-sm hover:bg-blue-200">صبح</button>
          <button onClick={()=>handlePreview('evening')} className="bg-blue-100 text-blue-700 px-3 py-1 rounded text-sm hover:bg-blue-200">شب</button>
          <button onClick={()=>handlePreview('weekly')} className="bg-blue-100 text-blue-700 px-3 py-1 rounded text-sm hover:bg-blue-200">هفتگی</button>
        </div>
        {preview && (
          <div className="border rounded-lg p-4 bg-gray-50">
            <p className="font-bold text-sm mb-2">{preview.report_type}</p>
            <pre className="whitespace-pre-wrap text-sm">{preview.content}</pre>
            <div className="mt-3 flex gap-2">
              <button onClick={()=>handleSend(preview.report_type.split('_')[0])} className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700">ارسال به تلگرام</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
