import { create } from 'zustand'
import apiClient from '../services/apiClient'

const STORAGE_KEY = 'user'

function readStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/**
 * Store đăng nhập (Zustand).
 * Lưu access_token ở localStorage để F5 không mất phiên — server vẫn là
 * nguồn kiểm soát thời gian, localStorage chỉ giữ token.
 */
const useAuthStore = create((set, get) => ({
  user: readStoredUser(),
  token: localStorage.getItem('access_token'),
  loading: false,

  isAuthenticated: () => Boolean(get().token),

  role: () => get().user?.role?.code || null,

  async login(username, password) {
    set({ loading: true })
    try {
      const { data } = await apiClient.post('/auth/login', { username, password })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data.user))
      set({ user: data.user, token: data.access_token, loading: false })
      return data.user
    } catch (error) {
      set({ loading: false })
      throw error
    }
  },

  logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem(STORAGE_KEY)
    set({ user: null, token: null })
  },
}))

export default useAuthStore
