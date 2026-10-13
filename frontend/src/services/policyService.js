import apiClient from './apiClient'

/**
 * Giá trị mặc định của bộ cấu hình khoá an toàn.
 * PHẢI khớp với `ExamSecurityConfig` phía backend (app/schemas/settings_schema.py).
 * Khi backend trả về policy, giá trị này chỉ là dự phòng cho lúc đang tải.
 */
export const DEFAULT_SECURITY_CONFIG = {
  require_fullscreen: true,
  block_copy_paste: true,
  block_devtools: true,
  detect_devtools: true,
  monitor_tab_switch: true,
  lock_navigation: true,
  disable_print: true,
  allow_web_fallback: true,
  max_tab_switch: 5,
  max_fullscreen_exit: 3,
  auto_submit_on_threshold: true,
  warn_countdown_seconds: 10,
}

/** Nhãn tiếng Việt cho từng cơ chế khoá — dùng ở form cấu hình và ở Exam Room. */
export const SECURITY_MECHANISM_LABELS = {
  require_fullscreen: {
    label: 'Toàn màn hình',
    description: 'Bắt thí sinh vào chế độ toàn màn hình khi bắt đầu thi.',
    short: 'Toàn màn hình',
  },
  block_copy_paste: {
    label: 'Chặn copy / paste',
    description: 'Chặn sao chép, dán và cắt văn bản trong trang thi.',
    short: 'Chặn copy',
  },
  block_devtools: {
    label: 'Chặn DevTools',
    description: 'Chặn F12 và các tổ hợp phím mở công cụ phát triển.',
    short: 'Chặn DevTools',
  },
  detect_devtools: {
    label: 'Phát hiện DevTools',
    description: 'Ghi nhận sự kiện khi DevTools được mở (chỉ phát hiện, không chặn tuyệt đối).',
    short: 'Phát hiện DevTools',
  },
  monitor_tab_switch: {
    label: 'Theo dõi chuyển tab',
    description: 'Ghi nhận khi thí sinh rời khỏi tab thi (phát hiện sau khi xảy ra).',
    short: 'Giám sát tab',
  },
  lock_navigation: {
    label: 'Khoá điều hướng',
    description: 'Chặn điều hướng ra khỏi trang thi và mở cửa sổ mới.',
    short: 'Khoá điều hướng',
  },
  disable_print: {
    label: 'Chặn in',
    description: 'Chặn thao tác in trang từ trình duyệt.',
    short: 'Chặn in',
  },
}

/** Danh sách cơ chế dạng toggle, dùng để render form cấu hình. */
export const TOGGLE_MECHANISMS = [
  'require_fullscreen',
  'block_copy_paste',
  'block_devtools',
  'detect_devtools',
  'monitor_tab_switch',
  'lock_navigation',
  'disable_print',
]

/**
 * Service đọc/ghi cấu hình khoá an toàn.
 * Đây là nơi DUY NHẤT frontend gọi tới các endpoint cấu hình — mọi hook khoá an toàn
 * đều nhận policy từ đây, không hardcode (skills.md Quy tắc #3).
 */
export const policyService = {
  // --- Cấp hệ thống (Admin) ---
  async getSystemSettings() {
    const { data } = await apiClient.get('/admin/settings')
    return data
  },

  async setRequireSafeBrowserGlobal(value) {
    const { data } = await apiClient.put('/admin/settings/require-safe-browser', { value })
    return data.value
  },

  async setSebClientConfig(config) {
    const { data } = await apiClient.put('/admin/settings/seb-client-config', config)
    return data
  },

  async setDefaultSecurityConfig(config) {
    const { data } = await apiClient.put('/admin/settings/default-security-config', config)
    return data
  },

  // --- Cấp đề (Teacher) ---
  async getExamPolicy(examId) {
    const { data } = await apiClient.get(`/exams/${examId}/security-policy`)
    return data
  },

  async setExamPolicy(examId, config) {
    const { data } = await apiClient.put(`/exams/${examId}/security-policy`, config)
    return data
  },

  // --- Vào phòng thi (Student) ---
  // Server trả policy đã resolve trong response của join, nên
  // useSecurityPolicy chỉ cần đọc từ state, không gọi endpoint riêng.
  normalize(policy) {
    if (!policy) return { ...DEFAULT_SECURITY_CONFIG }
    // Gộp với mặc định để field mới thêm sau này không làm vỡ client cũ
    return { ...DEFAULT_SECURITY_CONFIG, ...policy }
  },
}

export default policyService
