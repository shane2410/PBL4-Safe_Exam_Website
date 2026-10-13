import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '../../components/common/Icon'
import Input from '../../components/common/Input'
import Alert from '../../components/common/Alert'
import useAuthStore from '../../store/authStore'
import { extractErrorMessage } from '../../services/apiClient'

/** Điều hướng về trang chính đúng theo vai trò sau khi đăng nhập. */
const HOME_BY_ROLE = {
  ADMIN: '/admin',
  TEACHER: '/teacher',
  STUDENT: '/exam/join',
}

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  const login = useAuthStore((s) => s.login)
  const loading = useAuthStore((s) => s.loading)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const user = await login(username, password)
      navigate(HOME_BY_ROLE[user.role.code] || '/', { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err, 'Đăng nhập thất bại. Kiểm tra lại tài khoản.'))
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-[400px]">
        <div className="bg-white rounded-lg shadow-medium border border-slate-200 p-8">
          <div className="text-center mb-7">
            <div className="w-12 h-12 mx-auto rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center">
              <Icon name="shield" size={24} className="text-primary" filled />
            </div>
            <h1 className="font-headline-lg font-bold text-slate-900 mt-4">
              Đăng nhập hệ thống thi
            </h1>
            <p className="text-slate-500 mt-1.5">
              Hệ thống thi trắc nghiệm trực tuyến an toàn
            </p>
          </div>

          {error && <Alert variant="error" className="mb-5">{error}</Alert>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Tên đăng nhập"
              value={username}
              onChange={setUsername}
              placeholder="Nhập tên đăng nhập"
              autoComplete="username"
              required
            />

            <div className="relative">
              <Input
                label="Mật khẩu"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={setPassword}
                placeholder="Nhập mật khẩu"
                autoComplete="current-password"
                required
                className="[&_input]:pr-11"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-[34px] text-slate-400 hover:text-slate-600 transition-colors"
                title={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                <Icon name={showPassword ? 'visibility_off' : 'visibility'} size={18} />
              </button>
            </div>

            <button type="submit" disabled={loading} className="btn-primary w-full btn-lg">
              {loading ? 'Đang đăng nhập…' : 'Đăng nhập'}
            </button>
          </form>
        </div>

        <Alert variant="info" className="mt-4">
          Phiên thi được giám sát và ghi nhận vi phạm.
        </Alert>
      </div>
    </div>
  )
}
