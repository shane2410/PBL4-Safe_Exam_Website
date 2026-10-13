import { useEffect, useRef } from 'react'

/**
 * Nhóm 2 — CHỈ PHÁT HIỆN ĐƯỢC (skills.md Quy tắc #3).
 *
 * Theo dõi `visibilitychange` và `blur` để ghi nhận thí sinh rời khỏi tab thi.
 * KHÔNG chặn được hành động: Alt+Tab / phím Win do HỆ ĐIỀU HÀNH xử lý trước khi
 * sự kiện tới được trình duyệt. Ta chỉ biết hậu quả SAU KHI đã xảy ra.
 *
 * `blur` bị trễ hơn và kém tin cậy hơn `visibilitychange` (một số trình duyệt/OS
 * báo khác nhau), nên dùng làm cơ chế dự phòng — có khoảng debounce để tránh
 * ghi nhận trùng cho cùng một lần rời tab.
 */
export function useVisibilityMonitor({ enabled, onAway, debounceMs = 1200 }) {
  const lastReportRef = useRef(0)

  useEffect(() => {
    if (!enabled) return undefined

    const report = (source) => {
      const now = Date.now()
      // Tránh ghi nhận trùng khi blur và visibilitychange cùng bắn cho 1 sự kiện
      if (now - lastReportRef.current < debounceMs) return
      lastReportRef.current = now
      // Không tự ghi vi phạm ở đây — ExamRoom gom về handleIncident để một
      // hành động rời đi (rời tab + thoát fullscreen) chỉ bị tính MỘT lần.
      onAway?.(source)
    }

    const onVisibility = () => {
      if (document.hidden) report('visibilitychange')
    }
    const onBlur = () => report('window_blur')

    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)

    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
    }
  }, [enabled, onAway, debounceMs])

  return {}
}

export default useVisibilityMonitor
