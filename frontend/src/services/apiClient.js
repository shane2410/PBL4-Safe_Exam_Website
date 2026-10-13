import axios from 'axios'

/**
 * Axios client dùng chung cho toàn hệ thống.
 * - Tự gắn access_token từ store.
 * - Tự gắn header định danh client: web client gửi `web`; SEB Client sẽ gửi `seb`
 *   và kèm chữ ký HMAC (Phase 1). Ở Lớp A (web) ta luôn khai báo trung thực là `web`
 *   — server không tin header này, nó dùng challenge-response để xác minh (Quy tắc #4).
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

export const CLIENT_TYPE = 'web'

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  config.headers['X-Client-Type'] = CLIENT_TYPE
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Token hết hạn hoặc bị thu hồi -> đưa về trang đăng nhập.
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

/** Trích message lỗi thân thiện từ response của FastAPI. */
export function extractErrorMessage(error, fallback = 'Đã có lỗi xảy ra, vui lòng thử lại.') {
  const detail = error?.response?.data?.detail
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  // FastAPI trả mảng lỗi validation dạng [{loc, msg, type}]
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => d.msg || d).join('; ')
  }
  return fallback
}

export default apiClient
