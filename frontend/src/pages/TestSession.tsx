import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { testAPI } from '../api/client'

export default function TestSession() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState<any>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [timeLeft, setTimeLeft] = useState<number | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const timerRef = useRef<any>(null)

  useEffect(() => {
    if (!id) return
    testAPI.getSession(Number(id)).then(res => {
      setSession(res.data)
      setLoading(false)
      // Initialize answers from session
      const ans: Record<number, string> = {}
      res.data.questions?.forEach((sq: any) => {
        if (sq.user_answer) ans[sq.question_id] = sq.user_answer
      })
      setAnswers(ans)

      if (res.data.mode === 'timed' && res.data.time_limit_seconds) {
        setTimeLeft(res.data.time_limit_seconds)
      }
    }).catch(err => {
      console.error(err)
      setLoading(false)
    })
  }, [id])

  useEffect(() => {
    // Elapsed timer always
    const interval = setInterval(() => {
      setElapsed(prev => prev + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (timeLeft === null) return
    if (timeLeft <= 0) {
      handleFinish()
      return
    }
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => (prev !== null ? prev - 1 : null))
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [timeLeft])

  const handleAnswer = async (questionId: number, answer: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: answer }))
    try {
      await testAPI.submitAnswer(Number(id), { question_id: questionId, answer })
    } catch (err) {
      console.error(err)
    }
  }

  const handleFinish = async () => {
    if (submitting) return
    setSubmitting(true)
    try {
      await testAPI.finish(Number(id), { elapsed_seconds: elapsed })
      navigate(`/test/${id}/result`)
    } catch (err) {
      console.error(err)
      setSubmitting(false)
    }
  }

  if (loading) return <div className="p-6">در حال بارگذاری...</div>
  if (!session) return <div className="p-6">آزمون یافت نشد</div>

  const currentQ = session.questions?.[currentIndex]
  if (!currentQ) return <div className="p-6">سوالی یافت نشد</div>

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6" dir="rtl">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-4 flex justify-between items-center">
        <div>
          <h1 className="font-bold">{session.title || `آزمون #${session.id}`}</h1>
          <p className="text-sm text-gray-500">سوال {currentIndex + 1} از {session.total_questions}</p>
        </div>
        <div className="flex gap-4 items-center">
          {session.mode === 'timed' && timeLeft !== null ? (
            <div className={`px-3 py-1 rounded-lg font-bold ${timeLeft < 300 ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'}`}>
              ⏱️ {formatTime(timeLeft)}
            </div>
          ) : (
            <div className="px-3 py-1 rounded-lg bg-gray-100 text-gray-600 text-sm">
              بدون زمان / Untimed - سپری شده: {formatTime(elapsed)}
            </div>
          )}
          <button
            onClick={handleFinish}
            disabled={submitting}
            className="bg-green-600 text-white px-4 py-1 rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            پایان آزمون
          </button>
        </div>
      </div>

      {/* Progress */}
      <div className="bg-white rounded-lg shadow p-2">
        <div className="flex gap-1">
          {session.questions?.map((sq: any, idx: number) => (
            <button
              key={sq.id}
              onClick={() => setCurrentIndex(idx)}
              className={`flex-1 h-2 rounded ${
                idx === currentIndex ? 'bg-blue-600' : answers[sq.question_id] ? 'bg-green-500' : 'bg-gray-200'
              }`}
              title={`سوال ${idx + 1}`}
            />
          ))}
        </div>
      </div>

      {/* Question */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="mb-6">
          <p className="text-sm text-gray-500 mb-2">سوال {currentIndex + 1} - {currentQ.question?.stable_id}</p>
          <p className="text-lg font-medium leading-relaxed">
            {currentQ.question?.question_text_fa || currentQ.question?.question_text || 'متن سوال موجود نیست'}
          </p>
          {currentQ.question?.image_url && (
            <img src={currentQ.question.image_url} alt="question" className="mt-4 max-w-full rounded" />
          )}
        </div>

        <div className="space-y-3">
          {['A', 'B', 'C', 'D'].map(opt => {
            const text = currentQ.question?.[`option_${opt.toLowerCase()}` as keyof typeof currentQ.question] as string
            if (!text) return null
            const isSelected = answers[currentQ.question_id] === opt
            return (
              <button
                key={opt}
                onClick={() => handleAnswer(currentQ.question_id, opt)}
                className={`w-full text-right p-4 border rounded-lg flex items-center gap-3 transition-colors ${
                  isSelected ? 'bg-blue-50 border-blue-500 text-blue-700' : 'bg-white border-gray-200 hover:bg-gray-50'
                }`}
              >
                <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  isSelected ? 'bg-blue-600 text-white' : 'bg-gray-100'
                }`}>
                  {opt}
                </span>
                <span>{text}</span>
              </button>
            )
          })}
        </div>

        <div className="mt-6 flex justify-between">
          <button
            onClick={() => setCurrentIndex(prev => Math.max(0, prev - 1))}
            disabled={currentIndex === 0}
            className="px-4 py-2 border rounded-lg disabled:opacity-50 hover:bg-gray-50"
          >
            ← قبلی
          </button>
          <button
            onClick={() => setCurrentIndex(prev => Math.min((session.questions?.length || 1) - 1, prev + 1))}
            disabled={currentIndex === (session.questions?.length || 1) - 1}
            className="px-4 py-2 border rounded-lg disabled:opacity-50 hover:bg-gray-50"
          >
            بعدی →
          </button>
        </div>
      </div>

      {/* Unanswered warning */}
      <div className="bg-yellow-50 p-3 rounded-lg text-sm text-yellow-800">
        💡 پاسخ‌های ثبت نشده به عنوان نزده باقی می‌مانند و اشتباه محسوب نمی‌شوند
      </div>
    </div>
  )
}
