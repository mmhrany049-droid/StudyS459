import { useEffect, useState } from 'react'
import { academicAPI, booksAPI } from '../api/client'

export default function Classes() {
  const [sessions, setSessions] = useState<any[]>([])
  const [lessons, setLessons] = useState<any[]>([])
  const [formSession, setFormSession] = useState({ date: new Date().toISOString().split('T')[0], title: '', attended: true, notes: '' })
  const [formLesson, setFormLesson] = useState({ taught_date: new Date().toISOString().split('T')[0], title: '', notes: '', book_id: '', book_node_id: '' })
  const [books, setBooks] = useState<any[]>([])
  const [nodes, setNodes] = useState<any[]>([])

  const load = () => {
    academicAPI.classSessions.list().then(res => setSessions(res.data))
    academicAPI.taughtLessons.list().then(res => setLessons(res.data))
    booksAPI.listBooks().then(res => setBooks(res.data))
  }
  useEffect(()=>{ load() },[])

  useEffect(()=>{
    if(formLesson.book_id){
      booksAPI.getNodes(Number(formLesson.book_id)).then(res=>{
        // flatten tree
        const flat: any[] = []
        const traverse = (arr:any[])=>{
          arr.forEach(n=>{
            flat.push(n)
            if(n.children) traverse(n.children)
          })
        }
        traverse(res.data)
        setNodes(flat)
      })
    }
  },[formLesson.book_id])

  const handleCreateSession = async (e:React.FormEvent)=>{
    e.preventDefault()
    await academicAPI.classSessions.create(formSession)
    load()
  }
  const handleCreateLesson = async (e:React.FormEvent)=>{
    e.preventDefault()
    const data:any = {...formLesson}
    if(data.book_id) data.book_id = Number(data.book_id)
    if(data.book_node_id) data.book_node_id = Number(data.book_node_id)
    else delete data.book_node_id
    if(!data.book_id) delete data.book_id
    await academicAPI.taughtLessons.create(data)
    load()
  }

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">کلاس‌ها و دروس تدریس شده</h1>
      
      <div className="bg-red-50 border border-red-200 p-4 rounded-lg text-sm">
        <p className="font-bold text-red-800">قانون مهم: TAUGHT ≠ LEARNED</p>
        <p>ثبت اینکه معلم درسی را تدریس کرده، به معنای افزایش خودکار تسلط نیست. تدریس شواهدی از مواجهه/زمینه است، نه اثبات یادگیری.</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">ثبت جلسه کلاس</h2>
          <form onSubmit={handleCreateSession} className="space-y-3">
            <input type="date" value={formSession.date} onChange={e=>setFormSession({...formSession,date:e.target.value})} className="border rounded px-3 py-2 w-full" required />
            <input value={formSession.title} onChange={e=>setFormSession({...formSession,title:e.target.value})} placeholder="عنوان جلسه" className="border rounded px-3 py-2 w-full" />
            <textarea value={formSession.notes} onChange={e=>setFormSession({...formSession,notes:e.target.value})} placeholder="یادداشت‌ها" className="border rounded px-3 py-2 w-full" />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={formSession.attended} onChange={e=>setFormSession({...formSession,attended:e.target.checked})} /> حضور داشتم</label>
            <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">ثبت جلسه</button>
          </form>
          <div className="mt-4 space-y-2">
            {sessions.map(s=>(
              <div key={s.id} className="text-sm p-2 border rounded">
                <p className="font-medium">{s.title || 'جلسه'} - {s.date}</p>
                <p className="text-xs text-gray-500">{s.attended ? 'حاضر' : 'غایب'} - {s.notes}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">ثبت درس تدریس شده</h2>
          <form onSubmit={handleCreateLesson} className="space-y-3">
            <input type="date" value={formLesson.taught_date} onChange={e=>setFormLesson({...formLesson,taught_date:e.target.value})} className="border rounded px-3 py-2 w-full" required />
            <select value={formLesson.book_id} onChange={e=>setFormLesson({...formLesson,book_id:e.target.value})} className="border rounded px-3 py-2 w-full">
              <option value="">انتخاب کتاب (اختیاری)</option>
              {books.map(b=> <option key={b.id} value={b.id}>{b.title_fa || b.title}</option>)}
            </select>
            {nodes.length>0 && (
              <select value={formLesson.book_node_id} onChange={e=>setFormLesson({...formLesson,book_node_id:e.target.value})} className="border rounded px-3 py-2 w-full">
                <option value="">انتخاب مبحث (اختیاری)</option>
                {nodes.map(n=> <option key={n.id} value={n.id}>{n.title_fa || n.title} ({n.node_type})</option>)}
              </select>
            )}
            <input value={formLesson.title} onChange={e=>setFormLesson({...formLesson,title:e.target.value})} placeholder="عنوان درس" className="border rounded px-3 py-2 w-full" />
            <textarea value={formLesson.notes} onChange={e=>setFormLesson({...formLesson,notes:e.target.value})} placeholder="یادداشت‌ها" className="border rounded px-3 py-2 w-full" />
            <button type="submit" className="w-full bg-green-600 text-white py-2 rounded hover:bg-green-700">ثبت درس تدریس شده - تسلط افزایش نمی‌یابد</button>
          </form>
          <div className="mt-4 space-y-2">
            {lessons.map(l=>(
              <div key={l.id} className="text-sm p-2 border rounded">
                <p className="font-medium">{l.title || 'درس'} - {l.taught_date}</p>
                <p className="text-xs text-gray-500">{l.book_title} - {l.node_title}</p>
                <p className="text-xs text-gray-500">{l.notes}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
