import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../../components/common/Icon'
import Alert from '../../components/common/Alert'
import teacherService from '../../services/teacherService'
import { formatDateTime } from '../../utils/labels'

const MODULES = [
  {
    to: '/teacher/questions',
    icon: 'description',
    title: 'Ngân hàng câu hỏi',
    desc: 'Tạo và quản lý câu hỏi theo môn học, độ khó và loại.',
  },
  {
    to: '/teacher/exams',
    icon: 'school',
    title: 'Đề thi',
    desc: 'Tạo đề thi, thêm câu hỏi và bật cờ yêu cầu Safe Exam Browser.',
  },
  {
    to: '/teacher/schedules',
    icon: 'event',
    title: 'Lịch thi',
    desc: 'Tạo ca thi, sinh mã phòng và phân công giám thị.',
  },
  {
    to: '/teacher/reports',
    icon: 'query_stats',
    title: 'Báo cáo',
    desc: 'Thống kê điểm, xuất Excel/PDF và tra cứu nhật ký vi phạm.',
  },
]

/** Trang chủ giảng viên — kèm tóm tắt nhanh các ca thi sắp diễn ra. */
export default function TeacherHome() {
  const [schedules, setSchedules] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    teacherService
      .getSchedules()
      .then(setSchedules)
      .catch(() => setError('Không tải được danh sách ca thi.'))
  }, [])

  const ongoing = schedules.filter((s) => s.status === 'ONGOING')

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="space-y-1">
          <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
            Tổng quan giảng viên
          </h1>
          <p className="text-slate-600">Quản lý đề thi, lịch thi và kết quả.</p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        {/* Ca đang diễn ra — đường tắt tới màn giám sát */}
        {ongoing.length > 0 && (
          <div className="card p-5 border-l-4 border-l-success">
            <div className="flex items-center gap-2 mb-3">
              <Icon name="monitoring" size={20} className="text-success" />
              <h2 className="font-headline-sm font-semibold text-slate-800">
                Ca thi đang diễn ra
              </h2>
            </div>
            <ul className="space-y-2">
              {ongoing.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <code className="px-2 py-0.5 rounded bg-primary-50 text-primary-700 text-xs font-medium">
                      {s.room_code}
                    </code>
                    <span className="ml-2 text-sm text-slate-700">{s.exam?.title}</span>
                    <span className="ml-2 text-xs text-slate-400">
                      {formatDateTime(s.start_time)}
                    </span>
                  </div>
                  <Link
                    to={`/monitor/${s.id}?room=${s.room_code}`}
                    className="btn-primary btn-sm flex-shrink-0"
                  >
                    <Icon name="monitoring" size={16} />
                    Giám sát
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {MODULES.map((m) => (
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
