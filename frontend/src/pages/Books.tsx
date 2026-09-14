import { useEffect, useState } from 'react'
import { booksAPI } from '../api/client'

export default function Books() {
  const [books, setBooks] = useState<any[]>([])
  const [subjects, setSubjects] = useState<any[]>([])
  const [activations, setActivations] = useState<any[]>([])
  const [selectedBook, setSelectedBook] = useState<any>(null)
  const [nodes, setNodes] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      booksAPI.listBooks(),
      booksAPI.listSubjects(),
      booksAPI.getActivations()
    ]).then(([booksRes, subjectsRes, actRes]) => {
      setBooks(booksRes.data)
      setSubjects(subjectsRes.data)
      setActivations(actRes.data)
      setLoading(false)
    }).catch(err => {
      console.error(err)
      setLoading(false)
    })
  }, [])

  const handleActivate = async (bookId: number, isActive: boolean) => {
    try {
      await booksAPI.activate(bookId, isActive)
      const actRes = await booksAPI.getActivations()
      setActivations(actRes.data)
    } catch (err) {
      console.error(err)
    }
  }

  const handleSelectBook = async (book: any) => {
    setSelectedBook(book)
    try {
      const res = await booksAPI.getNodes(book.id)
      setNodes(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  const isBookActive = (bookId: number) => {
    const act = activations.find(a => a.book_id === bookId)
    return act ? act.is_active : false
  }

  const renderNodeTree = (nodes: any[], level = 0) => {
    return nodes.map(node => (
      <div key={node.id} style={{ marginRight: level * 20 }} className="border-r-2 border-gray-200 pr-3 py-1">
        <div className="flex items-center gap-2">
          <span className="text-xs bg-gray-100 px-2 py-1 rounded">{node.node_type}</span>
          <span className="font-medium">{node.title_fa || node.title}</span>
          <span className="text-xs text-gray-500">{node.stable_id}</span>
        </div>
        {node.children && node.children.length > 0 && (
          <div className="mt-1">
            {renderNodeTree(node.children, level + 1)}
          </div>
        )}
      </div>
    ))
  }

  if (loading) return <div>در حال بارگذاری...</div>

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">کتاب‌ها</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">لیست کتاب‌ها</h2>
          <div className="space-y-3">
            {books.map(book => (
              <div key={book.id} className="border rounded-lg p-4 flex justify-between items-start">
                <div className="flex-1">
                  <p className="font-bold">{book.title_fa || book.title}</p>
                  <p className="text-sm text-gray-600">{book.publisher} - {book.stable_id}</p>
                  <p className="text-xs text-gray-500 mt-1">{book.description}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => handleSelectBook(book)}
                      className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded hover:bg-blue-200"
                    >
                      مشاهده ساختار
                    </button>
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={isBookActive(book.id)}
                      onChange={e => handleActivate(book.id, e.target.checked)}
                      className="rounded"
                    />
                    فعال
                  </label>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">ساختار کتاب {selectedBook ? `- ${selectedBook.title_fa}` : ''}</h2>
          {selectedBook ? (
            nodes.length > 0 ? (
              <div className="space-y-1">
                {renderNodeTree(nodes)}
              </div>
            ) : (
              <p className="text-gray-500 text-sm">ساختاری یافت نشد</p>
            )
          ) : (
            <p className="text-gray-500 text-sm">کتابی را انتخاب کنید</p>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">دروس</h2>
        <div className="grid grid-cols-3 gap-4">
          {subjects.map(sub => (
            <div key={sub.id} className="p-3 rounded-lg" style={{ backgroundColor: sub.color + '20', borderColor: sub.color, borderWidth: 1 }}>
              <p className="font-bold">{sub.name_fa || sub.name}</p>
              <p className="text-xs text-gray-600">{sub.stable_id}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
