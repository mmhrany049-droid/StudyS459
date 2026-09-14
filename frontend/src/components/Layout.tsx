import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { authAPI } from '../api/client'

interface LayoutProps {
  children: React.ReactNode
}

const navItems = [
  { path: '/', label: 'داشبورد', labelEn: 'Dashboard', icon: '🏠' },
  { path: '/today', label: 'امروز', labelEn: 'Today', icon: '📅' },
  { path: '/week', label: 'هفته', labelEn: 'Week', icon: '🗓️' },
  { path: '/goals', label: 'اهداف', labelEn: 'Goals', icon: '🎯' },
  { path: '/student-state', label: 'وضعیت', labelEn: 'State', icon: '🧠' },
  { path: '/test', label: 'آزمون', labelEn: 'Test', icon: '📝' },
  { path: '/progress', label: 'پیشرفت', labelEn: 'Progress', icon: '📊' },
  { path: '/analytics', label: 'تحلیل', labelEn: 'Analytics', icon: '📈' },
  { path: '/review', label: 'مرور', labelEn: 'Review', icon: '🔁' },
  { path: '/books', label: 'کتاب‌ها', labelEn: 'Books', icon: '📚' },
  { path: '/schedule', label: 'برنامه', labelEn: 'Schedule', icon: '⏰' },
  { path: '/classes', label: 'کلاس‌ها', labelEn: 'Classes', icon: '🏫' },
  { path: '/homework', label: 'تکالیف', labelEn: 'Homework', icon: '📋' },
  { path: '/exams', label: 'امتحانات', labelEn: 'Exams', icon: '🎓' },
  { path: '/friends', label: 'دوستان', labelEn: 'Friends', icon: '👥' },
  { path: '/telegram', label: 'تلگرام', labelEn: 'Telegram', icon: '✈️' },
  { path: '/settings', label: 'تنظیمات', labelEn: 'Settings', icon: '⚙️' },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      navigate('/login')
      return
    }
    authAPI.me().then(res => setUser(res.data)).catch(() => {
      localStorage.removeItem('access_token')
      navigate('/login')
    })
  }, [navigate])

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    navigate('/login')
  }

  if (location.pathname === '/login' || location.pathname === '/register') {
    return <>{children}</>
  }

  return (
    <div className="min-h-screen bg-gray-50 flex" dir="rtl">
      {/* Sidebar */}
      <aside className="w-64 bg-white shadow-lg fixed h-full overflow-y-auto">
        <div className="p-6 border-b">
          <h1 className="text-xl font-bold text-gray-800">StudyS459</h1>
          <p className="text-sm text-gray-500 mt-1">سیستم مدیریت مطالعه</p>
          {user && (
            <div className="mt-3 text-sm">
              <p className="font-medium">{user.full_name || user.username}</p>
              <p className="text-gray-500 text-xs">{user.email}</p>
            </div>
          )}
        </div>
        <nav className="p-4">
          <ul className="space-y-1">
            {navItems.map(item => {
              const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                      isActive ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
          <div className="mt-8 pt-4 border-t">
            <button
              onClick={handleLogout}
              className="w-full text-right px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
            >
              🚪 خروج
            </button>
          </div>
        </nav>
      </aside>

      {/* Main */}
      <main className="flex-1 mr-64 p-6">
        <div className="max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  )
}
