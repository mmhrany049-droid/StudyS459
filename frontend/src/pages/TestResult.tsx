import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { testAPI } from '../api/client'

export default function TestResult() {
  const { id } = useParams()
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    testAPI.getResult(Number(id)).then(res => {
      setResult(res.data)
      setLoading(false)
    }).catch(err => {
      console.error(err)
      setLoading(false)
    })
  }, [id])

  if (loading) return <div className="p-6">در حال بارگذاری...</div>
  if (!result) return <div className="p-6">نتیجه یافت نشد</div>

  return (
    <div className="max-w-4xl mx-auto space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">نتیجه آزمون</h1>
      
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4 text-center">
          <p className="text-sm text-gray-500">کل</p>
          <p className="text-2xl font-bold">{result.total_questions}</p>
        </div>
        <div className="bg-green-50 rounded-lg shadow p-4 text-center">
          <p className="text-sm text-green-600">درست</p>
          <p className="text-2xl font-bold text-green-600">{result.correct_count}</p>
        </div>
        <div className="bg-red-50 rounded-lg shadow p-4 text-center">
          <p className="text-sm text-red-600">غلط</p>
          <p className="text-2xl font-bold text-red-600">{result.wrong_count}</p>
        </div>
        <div className="bg-gray-50 rounded-lg shadow p-4 text-center">
          <p className="text-sm text-gray-600">نزده</p>
          <p className="text-2xl font-bold text-gray-600">{result.unanswered_count}</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-bold">خلاصه</h2>
          <span className="text-lg font-bold text-blue-600">{result.accuracy?.toFixed(0) || 0}% دقت</span>
        </div>
        <p className="text-sm text-gray-600">زمان سپری شده: {result.elapsed_seconds ? `${Math.floor(result.elapsed_seconds/60)} دقیقه` : 'ثبت نشده'}</p>
        <p className="text-sm text-gray-600">وضعیت: {result.status === 'pending_correction' ? 'در انتظار تصحیح - کلید پاسخ ناقص' : 'تصحیح شده'}</p>
      </div>

      {result.topic_performance?.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">عملکرد بر اساس مبحث</h2>
          <div className="space-y-2">
            {result.topic_performance.map((tp: any) => (
              <div key={tp.book_node_id} className="flex justify-between items-center p-3 border rounded-lg">
                <span className="text-sm">{tp.node_title}</span>
                <div className="flex gap-4 text-sm">
                  <span className="text-green-600">{tp.correct}✓</span>
                  <span className="text-red-600">{tp.wrong}✗</span>
                  <span className="text-gray-500">{tp.unanswered} نزده</span>
                  <span className="font-bold">{tp.accuracy?.toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {result.difficulty_performance?.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">عملکرد بر اساس سطح دشواری</h2>
          <div className="space-y-2">
            {result.difficulty_performance.map((dp: any) => (
              <div key={dp.difficulty_level} className="flex justify-between items-center p-3 border rounded-lg">
                <span className="text-sm">سطح {dp.difficulty_level || 'نامشخص'}</span>
                <div className="flex gap-4 text-sm">
                  <span>{dp.total} سوال</span>
                  <span className="text-green-600">{dp.correct} درست</span>
                  <span className="font-bold">{dp.accuracy?.toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">بررسی سوال به سوال</h2>
        <div className="space-y-4">
          {result.questions?.map((sq: any, idx: number) => (
            <div key={sq.id} className={`border rounded-lg p-4 ${sq.is_correct === true ? 'bg-green-50 border-green-200' : sq.is_correct === false ? 'bg-red-50 border-red-200' : 'bg-gray-50'}`}>
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium">سوال {idx + 1} - {sq.question?.stable_id}</span>
                <span className="text-sm">
                  {sq.is_correct === true ? '✅ درست' : sq.is_correct === false ? '❌ غلط' : '⚪ نزده'}
                </span>
              </div>
              <p className="text-sm mb-2">{sq.question?.question_text_fa || sq.question?.question_text}</p>
              <div className="text-xs text-gray-600">
                <p>پاسخ شما: {sq.user_answer || 'نزده'} | پاسخ صحیح: {sq.question?.correct_option || 'نامشخص'}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-4">
        <Link to="/test" className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">آزمون جدید</Link>
        <Link to="/progress" className="border px-6 py-2 rounded-lg hover:bg-gray-50">مشاهده پیشرفت</Link>
        <Link to="/" className="border px-6 py-2 rounded-lg hover:bg-gray-50">داشبورد</Link>
      </div>
    </div>
  )
}
