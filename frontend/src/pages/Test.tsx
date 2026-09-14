import { useEffect, useState } from 'react'
import { booksAPI, testAPI } from '../api/client'
import { useNavigate } from 'react-router-dom'

export default function Test() {
  const [books, setBooks] = useState<any[]>([])
  const [selectedBook, setSelectedBook] = useState<number | ''>('')
  const [testSets, setTestSets] = useState<any[]>([])
  const [selectedTestSet, setSelectedTestSet] = useState<number | ''>('')
  const [mode, setMode] = useState<'timed' | 'untimed'>('timed')
  const [questionCount, setQuestionCount] = useState(10)
  const [timeLimit, setTimeLimit] = useState(30)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    booksAPI.listBooks().then(res => setBooks(res.data))
  }, [])

  useEffect(() => {
    if (selectedBook) {
      booksAPI.getTestSets(Number(selectedBook)).then(res => setTestSets(res.data))
    } else {
      setTestSets([])
    }
  }, [selectedBook])

  const handleCreate = async () => {
    setError('')
    setLoading(true)
    try {
      const data = {
        book_id: selectedBook ? Number(selectedBook) : undefined,
        test_set_id: selectedTestSet ? Number(selectedTestSet) : undefined,
        test_type: 'normal',
        mode: mode,
        time_limit_seconds: mode === 'timed' ? timeLimit * 60 : undefined,
        question_count: questionCount,
        title: `آزمون ${new Date().toLocaleDateString('fa-IR')}`
      }
      const res = await testAPI.createSession(data)
      navigate(`/test/${res.data.id}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'خطا در ایجاد آزمون')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl" dir="rtl">
      <h1 className="text-2xl font-bold">ایجاد آزمون جدید</h1>
      
      {error && (
        <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm">{error}</div>
      )}

      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">کتاب</label>
          <select
            value={selectedBook}
            onChange={e => setSelectedBook(e.target.value ? Number(e.target.value) : '')}
            className="w-full border rounded-lg px-3 py-2"
          >
            <option value="">انتخاب کتاب (اختیاری)</option>
            {books.map(b => (
              <option key={b.id} value={b.id}>{b.title_fa || b.title}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">مجموعه تست</label>
          <select
            value={selectedTestSet}
            onChange={e => setSelectedTestSet(e.target.value ? Number(e.target.value) : '')}
            className="w-full border rounded-lg px-3 py-2"
          >
            <option value="">انتخاب مجموعه (اختیاری)</option>
            {testSets.map(ts => (
              <option key={ts.id} value={ts.id}>{ts.title_fa || ts.title} - {ts.test_type} ({ts.question_count} سوال)</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">تعداد سوالات</label>
          <input
            type="number"
            min={1}
            max={50}
            value={questionCount}
            onChange={e => setQuestionCount(Number(e.target.value))}
            className="w-full border rounded-lg px-3 py-2"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">حالت آزمون</label>
          <div className="flex gap-4 mt-2">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="mode"
                checked={mode === 'timed'}
                onChange={() => setMode('timed')}
              />
              زمان‌دار
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="mode"
                checked={mode === 'untimed'}
                onChange={() => setMode('untimed')}
              />
              بدون زمان / Untimed
            </label>
          </div>
        </div>

        {mode === 'timed' && (
          <div>
            <label className="block text-sm font-medium mb-1">محدودیت زمانی (دقیقه)</label>
            <input
              type="number"
              min={1}
              value={timeLimit}
              onChange={e => setTimeLimit(Number(e.target.value))}
              className="w-full border rounded-lg px-3 py-2"
            />
          </div>
        )}

        <button
          onClick={handleCreate}
          disabled={loading}
          className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'در حال ایجاد...' : 'شروع آزمون'}
        </button>
      </div>

      <div className="bg-blue-50 p-4 rounded-lg text-sm">
        <p className="font-bold mb-2">نکات:</p>
        <ul className="list-disc list-inside space-y-1 text-gray-700">
          <li>سوالات به صورت تصادفی و بدون تکرار انتخاب می‌شوند</li>
          <li>در حالت بدون زمان، تایمر نمایش داده نمی‌شود و محدودیتی وجود ندارد</li>
          <li>زمان سپری شده برای تحلیل ثبت می‌شود</li>
          <li>پاسخ‌های ثبت نشده به عنوان نزده باقی می‌مانند و اشتباه محسوب نمی‌شوند</li>
        </ul>
      </div>
    </div>
  )
}
