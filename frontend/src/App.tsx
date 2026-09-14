import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Register from './pages/Register'
import Books from './pages/Books'
import Test from './pages/Test'
import TestSession from './pages/TestSession'
import TestResult from './pages/TestResult'
import Today from './pages/Today'
import Week from './pages/Week'
import Progress from './pages/Progress'
import Analytics from './pages/Analytics'
import Schedule from './pages/Schedule'
import Classes from './pages/Classes'
import Homework from './pages/Homework'
import Exams from './pages/Exams'
import Friends from './pages/Friends'
import Telegram from './pages/Telegram'
import Settings from './pages/Settings'
import Review from './pages/Review'

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Dashboard />} />
          <Route path="/today" element={<Today />} />
          <Route path="/week" element={<Week />} />
          <Route path="/test" element={<Test />} />
          <Route path="/test/:id" element={<TestSession />} />
          <Route path="/test/:id/result" element={<TestResult />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/review" element={<Review />} />
          <Route path="/books" element={<Books />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/classes" element={<Classes />} />
          <Route path="/homework" element={<Homework />} />
          <Route path="/exams" element={<Exams />} />
          <Route path="/friends" element={<Friends />} />
          <Route path="/telegram" element={<Telegram />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<div className="p-6">صفحه یافت نشد</div>} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
