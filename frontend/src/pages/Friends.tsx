import { useEffect, useState } from 'react'
import { socialAPI } from '../api/client'

export default function Friends() {
  const [groups, setGroups] = useState<any[]>([])
  const [form, setForm] = useState({ name: '', description: '', group_type: 'class' })
  const [inviteCode, setInviteCode] = useState('')
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null)
  const [members, setMembers] = useState<any[]>([])
  const [compareResult, setCompareResult] = useState<any[]>([])

  const load = () => {
    socialAPI.groups.list().then(res=> setGroups(res.data))
  }
  useEffect(()=>{ load() },[])

  const handleCreate = async (e: React.FormEvent)=>{
    e.preventDefault()
    await socialAPI.groups.create(form)
    load()
  }

  const handleJoin = async (e: React.FormEvent)=>{
    e.preventDefault()
    try{
      await socialAPI.groups.join(inviteCode)
      setInviteCode('')
      load()
    }catch(err:any){ alert(err.response?.data?.detail || 'خطا') }
  }

  const handleSelectGroup = async (groupId: number)=>{
    setSelectedGroup(groupId)
    const res = await socialAPI.groups.members(groupId)
    setMembers(res.data)
  }

  const handleCompare = async (metric: string)=>{
    if(!selectedGroup) return
    const res = await socialAPI.compare({ group_id: selectedGroup, metric })
    setCompareResult(res.data)
  }

  return (
    <div className="space-y-6" dir="rtl">
      <h1 className="text-2xl font-bold">دوستان و گروه‌ها</h1>
      
      <div className="bg-yellow-50 p-4 rounded-lg text-sm">
        <p className="font-bold">حریم خصوصی: به صورت پیش‌فرض خصوصی</p>
        <p>اطلاعات شما فقط با اجازه صریح به اشتراک گذاشته می‌شود. برنامه درسی خصوصی، یادداشت‌های خصوصی و اطلاعات شخصی هرگز بدون اجازه نمایش داده نمی‌شوند.</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">ایجاد گروه</h2>
          <form onSubmit={handleCreate} className="space-y-3">
            <input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="نام گروه" className="border rounded px-3 py-2 w-full" required />
            <input value={form.description} onChange={e=>setForm({...form,description:e.target.value})} placeholder="توضیحات" className="border rounded px-3 py-2 w-full" />
            <select value={form.group_type} onChange={e=>setForm({...form,group_type:e.target.value})} className="border rounded px-3 py-2 w-full">
              <option value="class">کلاس</option>
              <option value="study_group">گروه مطالعه</option>
              <option value="friends">دوستان</option>
            </select>
            <button type="submit" className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">ایجاد</button>
          </form>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-bold mb-4">پیوستن با کد دعوت</h2>
          <form onSubmit={handleJoin} className="space-y-3">
            <input value={inviteCode} onChange={e=>setInviteCode(e.target.value)} placeholder="کد دعوت" className="border rounded px-3 py-2 w-full" required />
            <button type="submit" className="w-full bg-green-600 text-white py-2 rounded hover:bg-green-700">پیوستن</button>
          </form>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="font-bold mb-4">گروه‌های من</h2>
        <div className="space-y-2">
          {groups.map(g=>(
            <div key={g.id} className="border rounded-lg p-4 flex justify-between items-center">
              <div>
                <p className="font-bold">{g.name} - {g.group_type}</p>
                <p className="text-sm text-gray-600">اعضا: {g.member_count} - کد دعوت: <span className="font-mono bg-gray-100 px-2 py-1 rounded">{g.invite_code}</span></p>
              </div>
              <button onClick={()=>handleSelectGroup(g.id)} className="bg-blue-100 text-blue-700 px-3 py-1 rounded text-sm hover:bg-blue-200">مشاهده اعضا</button>
            </div>
          ))}
        </div>
      </div>

      {selectedGroup && (
        <div className="grid grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="font-bold mb-4">اعضای گروه {selectedGroup}</h2>
            <div className="space-y-2">
              {members.map(m=>(
                <div key={m.id} className="p-2 border rounded text-sm">
                  <p className="font-medium">{m.full_name || m.username} - {m.role}</p>
                  <p className="text-xs text-gray-500">{m.joined_at}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="font-bold mb-4">مقایسه</h2>
            <p className="text-xs text-gray-500 mb-3">مقایسه نیاز به stable book/question IDs دارد و فقط با اجازه به اشتراک گذاری</p>
            <div className="flex gap-2 mb-4">
              <button onClick={()=>handleCompare('accuracy')} className="text-xs bg-blue-100 px-2 py-1 rounded hover:bg-blue-200">دقت</button>
              <button onClick={()=>handleCompare('tests_count')} className="text-xs bg-blue-100 px-2 py-1 rounded hover:bg-blue-200">تعداد تست</button>
              <button onClick={()=>handleCompare('coverage')} className="text-xs bg-blue-100 px-2 py-1 rounded hover:bg-blue-200">پوشش</button>
              <button onClick={()=>handleCompare('common_questions')} className="text-xs bg-blue-100 px-2 py-1 rounded hover:bg-blue-200">سوالات مشترک</button>
            </div>
            <div className="space-y-2">
              {compareResult.map((r:any)=>(
                <div key={r.user_id} className="flex justify-between text-sm p-2 bg-gray-50 rounded">
                  <span>{r.username}</span>
                  <span className="font-bold">{r.metric_value?.toFixed(1)} - {JSON.stringify(r.details)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
