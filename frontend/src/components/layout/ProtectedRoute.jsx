import { Navigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'

/**
 * Bảo vệ route phía client.
 *
 * LƯU Ý QUAN TRỌNG: đây chỉ là lớp trải nghiệm người dùng, KHÔNG phải bảo mật.
 * Mọi endpoint phía backend đều kiểm tra JWT + RBAC độc lập (skills.md Quy tắc #4.5),
 * nên gọi API trực tiếp bằng curl vẫn bị chặn đúng.
 */
export default function ProtectedRoute({ children, roles }) {
  const user = useAuthStore((s) => s.user)
  const token = useAuthStore((s) => s.token)

  if (!token || !user) {
    return <Navigate to="/login" replace />
  }

  if (roles && !roles.includes(user.role?.code)) {
    return <Navigate to="/" replace />
  }

  return children
}
