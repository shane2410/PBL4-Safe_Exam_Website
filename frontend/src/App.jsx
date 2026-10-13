import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

import Layout from './components/layout/Layout'
import ProtectedRoute from './components/layout/ProtectedRoute'

import Login from './pages/auth/Login'
import AdminHome from './pages/admin/AdminHome'
import Settings from './pages/admin/Settings'
import Users from './pages/admin/Users'
import AuditLog from './pages/admin/AuditLog'
import TeacherHome from './pages/teacher/TeacherHome'
import ExamList from './pages/teacher/ExamList'
import ExamEditor from './pages/teacher/ExamEditor'
import QuestionBank from './pages/teacher/QuestionBank'
import ScheduleList from './pages/teacher/ScheduleList'
import Reports from './pages/teacher/Reports'
import MonitorDashboard from './pages/monitor/MonitorDashboard'
import ExamJoin from './pages/exam/ExamJoin'
import ExamRoom from './pages/exam/ExamRoom'
import ExamResults from './pages/exam/ExamResults'

/**
 * Định tuyến của Lớp A (web).
 *
 * Lưu ý: ExamRoom nằm NGOÀI Layout vì khi thi, giao diện phải tối giản và dùng
 * toàn bộ không gian màn hình — không có sidebar.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* --- Khu vực Admin --- */}
        <Route
          element={
            <ProtectedRoute roles={['ADMIN']}>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/admin" element={<AdminHome />} />
          <Route path="/admin/settings" element={<Settings />} />
          <Route path="/admin/users" element={<Users />} />
          <Route path="/admin/audit-log" element={<AuditLog />} />
        </Route>

        {/* --- Khu vực Teacher --- */}
        <Route
          element={
            <ProtectedRoute roles={['TEACHER', 'ADMIN']}>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/teacher" element={<TeacherHome />} />
          <Route path="/teacher/exams" element={<ExamList />} />
          <Route path="/teacher/exams/:examId" element={<ExamEditor />} />
          <Route path="/teacher/questions" element={<QuestionBank />} />
          <Route path="/teacher/schedules" element={<ScheduleList />} />
          <Route path="/teacher/reports" element={<Reports />} />
        </Route>

        {/* --- Giám sát phòng thi ---
            Nằm ngoài Layout vì có thanh tiêu đề tối riêng và cần tối đa không gian. */}
        <Route
          path="/monitor/:scheduleId"
          element={
            <ProtectedRoute roles={['TEACHER', 'ADMIN']}>
              <MonitorDashboard />
            </ProtectedRoute>
          }
        />

        {/* --- Khu vực Thí sinh --- */}
        <Route
          element={
            <ProtectedRoute roles={['STUDENT', 'ADMIN', 'TEACHER']}>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route path="/exam/join" element={<ExamJoin />} />
          <Route path="/exam/results" element={<ExamResults />} />
        </Route>

        {/* Phòng thi: toàn màn hình, nằm ngoài Layout có sidebar */}
        <Route
          path="/exam/room"
          element={
            <ProtectedRoute>
              <ExamRoom />
            </ProtectedRoute>
          }
        />

        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
