import { Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import BookDetail from "@/pages/BookDetail";
import Books from "@/pages/Books";
import Dashboard from "@/pages/Dashboard";
import Placeholder from "@/pages/Placeholder";
import Progress from "@/pages/Progress";
import QuestionHistory from "@/pages/QuestionHistory";
import TestResult from "@/pages/TestResult";
import TestSession from "@/pages/TestSession";
import TestSetup from "@/pages/TestSetup";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="today" element={<Placeholder title="امروز" phase="Phase 5" />} />
        <Route path="week" element={<Placeholder title="هفته" phase="Phase 5" />} />
        <Route path="test" element={<TestSetup />} />
        <Route path="test/:id" element={<TestSession />} />
        <Route path="test/:id/result" element={<TestResult />} />
        <Route path="progress" element={<Progress />} />
        <Route path="questions/:id" element={<QuestionHistory />} />
        <Route path="books" element={<Books />} />
        <Route path="books/:id" element={<BookDetail />} />
        <Route
          path="schedule"
          element={<Placeholder title="برنامه مدرسه" phase="Phase 6" />}
        />
        <Route
          path="homework"
          element={<Placeholder title="تکالیف" phase="Phase 6" />}
        />
        <Route path="exams" element={<Placeholder title="امتحانات" phase="Phase 6" />} />
        <Route path="rewards" element={<Placeholder title="جوایز" phase="Phase 7" />} />
        <Route
          path="settings"
          element={<Placeholder title="تنظیمات" phase="Phase 8" />}
        />
        <Route
          path="*"
          element={<Placeholder title="یافت نشد" phase="—" />}
        />
      </Route>
    </Routes>
  );
}
