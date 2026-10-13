import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import Icon from '../common/Icon'
import useAuthStore from '../../store/authStore'

/**
 * Layout khung cho các trang quản trị (Admin / Teacher / Monitor).
 * Sidebar 260px nền navy #0F172A, không ẩn trên desktop.
 *
 * Danh sách menu được lọc theo vai trò — server vẫn là nơi kiểm tra quyền thật
 * (RBAC qua `require_role`), phần lọc ở đây chỉ để giảm rối giao diện.
 */
const MENU_BY_ROLE = {
  ADMIN: [
    { to: '/admin', icon: 'dashboard', label: 'Tổng quan', end: true },
    { to: '/admin/settings', icon: 'settings', label: 'Cấu hình hệ thống' },
    { to: '/admin/users', icon: 'manage_accounts', label: 'Người dùng' },
    { to: '/admin/audit-log', icon: 'history', label: 'Nhật ký' },
  ],
  TEACHER: [
    { to: '/teacher', icon: 'dashboard', label: 'Tổng quan', end: true },
    { to: '/teacher/questions', icon: 'description', label: 'Ngân hàng câu hỏi' },
    { to: '/teacher/exams', icon: 'school', label: 'Đề thi' },
    { to: '/teacher/schedules', icon: 'event', label: 'Lịch thi' },
    { to: '/teacher/reports', icon: 'query_stats', label: 'Báo cáo' },
  ],
  STUDENT: [
    { to: '/exam/join', icon: 'login', label: 'Vào phòng thi' },
    { to: '/exam/results', icon: 'query_stats', label: 'Kết quả của tôi' },
  ],
}

export default function Layout() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()

  const menu = MENU_BY_ROLE[user?.role?.code] || []

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <aside className="w-[260px] flex-shrink-0 bg-navy text-slate-300 flex flex-col justify-between border-r border-slate-800">
        <div className="flex flex-col">
          {/* Brand */}
          <div className="h-16 px-5 flex items-center gap-3 border-b border-slate-800 bg-navy">
            <div className="w-9 h-9 rounded-lg bg-primary/20 border border-primary/40 flex items-center justify-center text-primary-100">
              <Icon name="shield" size={20} filled />
            </div>
            <div className="flex flex-col">
              <span className="text-white font-headline-sm text-sm leading-snug">
                Hệ thống Khảo thí
              </span>
              <span className="text-slate-400 text-[11px] leading-tight">
                Bảo mật cấp học viện
              </span>
            </div>
          </div>

          {/* Menu */}
          <nav aria-label="Điều hướng chính" className="p-3 space-y-1.5">
            {menu.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary text-white shadow-sm'
                      : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon name={item.icon} size={20} />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Tài khoản */}
        <div className="p-3 border-t border-slate-800 bg-navy-deep">
          <div className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/60 flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-slate-200 text-xs font-semibold flex-shrink-0">
              {user?.full_name?.[0]?.toUpperCase() || '?'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-slate-100 text-xs font-medium truncate">{user?.full_name}</p>
              <p className="text-slate-400 text-[11px] truncate">{user?.role?.name}</p>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              title="Đăng xuất"
              className="text-slate-400 hover:text-white transition-colors flex-shrink-0"
            >
              <Icon name="logout" size={18} />
            </button>
          </div>
        </div>
      </aside>

      {/* Nội dung */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
