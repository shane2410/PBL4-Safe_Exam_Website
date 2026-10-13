import { Link } from 'react-router-dom'
import Card from '../../components/common/Card'
import Toggle from '../../components/common/Toggle'
import Icon from '../../components/common/Icon'
import useAuthStore from '../../store/authStore'
import { useEffect, useState } from 'react'
import policyService from '../../services/policyService'

/** Trang chủ Admin — tóm tắt cấu hình bảo mật quan trọng nhất. */
export default function AdminHome() {
  const user = useAuthStore((s) => s.user)
  const [requireSafeBrowser, setRequireSafeBrowser] = useState(null)

  useEffect(() => {
    policyService
      .getSystemSettings()
      .then((d) => setRequireSafeBrowser(Boolean(d.require_safe_browser_global)))
      .catch(() => setRequireSafeBrowser(null))
  }, [])

  const toggle = async (value) => {
    const prev = requireSafeBrowser
    setRequireSafeBrowser(value)
    try {
      await policyService.setRequireSafeBrowserGlobal(value)
    } catch {
      setRequireSafeBrowser(prev)
    }
  }

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="space-y-1">
          <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
            Xin chào, {user?.full_name}
          </h1>
          <p className="text-slate-600">Quản trị hệ thống thi trắc nghiệm an toàn.</p>
        </div>

        {/* Cờ bảo mật nổi bật */}
        <Card accent icon="security" title="Yêu cầu Safe Exam Browser">
          {requireSafeBrowser === null ? (
            <p className="text-slate-500 text-sm">Đang tải cấu hình…</p>
          ) : (
            <Toggle
              checked={requireSafeBrowser}
              onChange={toggle}
              label="Bắt buộc dùng Safe Exam Browser Client"
              description="Khi bật, các đề thi có cờ riêng sẽ chỉ nhận SEB Client đã xác thực. Thí sinh dùng web vẫn thi được nhưng ở chế độ hạn chế và bị ghi log phục tra."
            />
          )}
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[
            {
              to: '/admin/settings',
              icon: 'settings',
              title: 'Cấu hình hệ thống',
              desc: 'Bật/tắt yêu cầu Safe Exam Browser, cấu hình SEB Client và bộ cơ chế khoá an toàn mặc định.',
            },
            {
              to: '/teacher/exams',
              icon: 'school',
              title: 'Quản lý đề thi',
              desc: 'Tạo đề thi, thêm câu hỏi và cấu hình chính sách khoá an toàn cho từng đề.',
            },
            {
              to: '/teacher/schedules',
              icon: 'event',
              title: 'Lịch thi & Ca thi',
              desc: 'Tạo ca thi, sinh mã phòng và mở phòng giám sát thời gian thực.',
            },
            {
              to: '/teacher/reports',
              icon: 'query_stats',
              title: 'Báo cáo kết quả',
              desc: 'Xem điểm, điểm rủi ro, nhật ký vi phạm và xuất báo cáo Excel/PDF.',
            },
          ].map((m) => (
            <Link key={m.to} to={m.to} className="card p-6 hover:shadow-medium transition-shadow">
              <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center">
                <Icon name={m.icon} size={20} className="text-primary" />
              </div>
              <h2 className="font-headline-sm font-semibold text-slate-800 mt-4">{m.title}</h2>
              <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">{m.desc}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
