/** Nhãn tiếng Việt cho các giá trị enum trả về từ backend. */

export const QUESTION_TYPES = {
  SINGLE_CHOICE: 'Chọn một đáp án',
  MULTI_CHOICE: 'Chọn nhiều đáp án',
  FILL_BLANK: 'Nhập đáp án',
}

export const DIFFICULTIES = {
  EASY: { label: 'Dễ', tone: 'success' },
  MEDIUM: { label: 'Trung bình', tone: 'warning' },
  HARD: { label: 'Khó', tone: 'error' },
}

export const SCHEDULE_STATUS = {
  SCHEDULED: { label: 'Đã lên lịch', tone: 'neutral' },
  ONGOING: { label: 'Đang diễn ra', tone: 'success' },
  FINISHED: { label: 'Đã kết thúc', tone: 'primary' },
  CANCELLED: { label: 'Đã huỷ', tone: 'error' },
}

export const SESSION_STATUS = {
  IN_PROGRESS: { label: 'Đang làm bài', tone: 'success' },
  SUBMITTED: { label: 'Đã nộp bài', tone: 'neutral' },
  DISCONNECTED: { label: 'Mất kết nối', tone: 'warning' },
}

export const SUBMIT_TYPES = {
  MANUAL: 'Tự nộp',
  SHUTDOWN_BUTTON: 'Nộp từ nút kết thúc',
  AUTO_TIMEOUT: 'Tự động — hết giờ',
  AUTO_VIOLATION: 'Tự động — vi phạm',
}

/** Tên hiển thị của loại vi phạm. */
export const VIOLATION_LABELS = {
  TAB_SWITCH: 'Chuyển tab / rời cửa sổ',
  FULLSCREEN_EXIT: 'Thoát toàn màn hình',
  DEVTOOLS_DETECTED: 'Phát hiện DevTools',
  COPY_PASTE_ATTEMPT: 'Cố copy / paste',
  RIGHT_CLICK_ATTEMPT: 'Chuột phải',
  DUPLICATE_LOGIN: 'Đăng nhập trùng',
  CONNECTION_LOST: 'Mất kết nối',
  UNAUTHORIZED_CLIENT: 'Không dùng Safe Exam Browser',
}

/** Màu badge theo mức nghiêm trọng. */
export const SEVERITY_TONES = {
  LOW: 'neutral',
  MEDIUM: 'warning',
  HIGH: 'error',
}

/** Màu thanh điểm rủi ro theo ngưỡng. */
export function riskTone(score) {
  if (score >= 100) return 'error'
  if (score >= 50) return 'warning'
  return 'success'
}

export function riskBarColor(score) {
  if (score >= 100) return 'bg-error'
  if (score >= 50) return 'bg-warning'
  return 'bg-success'
}

/** Định dạng ngày giờ kiểu Việt Nam. */
export function formatDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Định dạng giây thành mm:ss. */
export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  const total = Math.max(0, Math.floor(seconds))
  const m = Math.floor(total / 60)
  const s = total % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h}h ${String(m % 60).padStart(2, '0')}m`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}
