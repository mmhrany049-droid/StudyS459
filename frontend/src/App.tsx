import { Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import BookDetail from "@/pages/BookDetail";
import Books from "@/pages/Books";
import Dashboard from "@/pages/Dashboard";
import ExamDetail from "@/pages/ExamDetail";
import Exams from "@/pages/Exams";
import Goals from "@/pages/Goals";
import Homework from "@/pages/Homework";
import Placeholder from "@/pages/Placeholder";
import Rewards from "@/pages/Rewards";
import Schedule from "@/pages/Schedule";
import Settings from "@/pages/Settings";
import Progress from "@/pages/Progress";
import QuestionHistory from "@/pages/QuestionHistory";
import TestResult from "@/pages/TestResult";
import TestSession from "@/pages/TestSession";
import TestSetup from "@/pages/TestSetup";
import Today from "@/pages/Today";
import Week from "@/pages/Week";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="today" element={<Today />} />
        <Route path="week" element={<Week />} />
        <Route path="test" element={<TestSetup />} />
        <Route path="test/:id" element={<TestSession />} />
        <Route path="test/:id/result" element={<TestResult />} />
        <Route path="progress" element={<Progress />} />
        <Route path="questions/:id" element={<QuestionHistory />} />
        <Route path="goals" element={<Goals />} />
        <Route path="books" element={<Books />} />
        <Route path="books/:id" element={<BookDetail />} />
        <Route path="schedule" element={<Schedule />} />
        <Route path="homework" element={<Homework />} />
        <Route path="exams" element={<Exams />} />
        <Route path="exams/:id" element={<ExamDetail />} />
        <Route path="rewards" element={<Rewards />} />
        <Route path="settings" element={<Settings />} />
        <Route
          path="*"
          element={<Placeholder title="یافت نشد" phase="—" />}
        />
      </Route>
    </Routes>
  );
}
