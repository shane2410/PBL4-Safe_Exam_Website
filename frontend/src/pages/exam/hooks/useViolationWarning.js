import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Mức 2 — CẢNH BÁO YÊU CẦU QUAY LẠI (SRS mục 5.6).
 *
 * Khi thí sinh rời khỏi tab hoặc thoát fullscreen, hệ thống cho một khoảng đếm
 * ngược để họ quay lại. Đồng hồ này CHỈ LÀ THỜI GIAN THÔNG BÁO — không phải
 * điều kiện quyết định có tính vi phạm hay không.
 *
 * Việc ĐẾM vi phạm do `handleIncident` ở ExamRoom đảm nhiệm: mỗi lần rời đi
 * tính đúng MỘT lần, cộng dồn theo ngưỡng `max_tab_switch` /
 * `max_fullscreen_exit` mà GV cấu hình. Hết ngưỡng thì SERVER tự nộp bài
 * (xem `AnticheatService.resolve_max_violations`).
 *
 * LƯU Ý THẬT TRUNG THỰC: đây là cơ chế RĂN ĐE. Không có cách nào buộc thí sinh
 * phải nhìn màn hình — họ có thể để cửa sổ cảnh báo chạy ở nền rồi đổi sang cửa sổ
 * khác. Vì vậy hệ thống KHÔNG coi việc ngồi ở cửa sổ cảnh báo là quay lại hợp lệ —
 * việc xác minh đó thuộc phúc tra.
 */

const WARNING_TYPES = ['TAB_SWITCH', 'FULLSCREEN_EXIT']

export function useViolationWarning({ policy }) {
  const [warning, setWarning] = useState(null)
  // deadline = thời điểm hết hạn (epoch ms), dùng đồng hồ client cho đếm ngược
  const deadlineRef = useRef(null)
  const [remaining, setRemaining] = useState(0)
  const reportedRef = useRef(false)

  const durationMs = (policy?.warn_countdown_seconds || 10) * 1000

  /** Gọi khi phát hiện vi phạm Nhóm 2 — mở cửa sổ cảnh báo và bắt đầu đếm. */
  const triggerWarning = useCallback(
    (eventType) => {
      if (!policy) return
      if (!WARNING_TYPES.includes(eventType)) return

      deadlineRef.current = Date.now() + durationMs
      reportedRef.current = false
      setRemaining(policy.warn_countdown_seconds || 10)
      setWarning(eventType)
      // KHÔNG ghi vi phạm ở đây.
      //
      // Trước đây hàm này ghi `warning_shown` ngay khi mở cảnh báo, rồi lại ghi
      // thêm `warning_ignored` khi hết giờ -> MỘT lần thoát fullscreen bị tính
      // thàm HAI vi phạm. Giờ việc đếm vi phạm do ExamRoom quyết định đúng một
      // lần qua handleIncident(); hook này chỉ lo phần hiển thị + đếm ngược.
    },
    [policy, durationMs],
  )

  /** Gọi khi thí sinh QUAY LẠI — huỷ cảnh báo, không tính vi phạm thêm. */
  const clearWarning = useCallback(() => {
    if (deadlineRef.current === null) return
    deadlineRef.current = null
    reportedRef.current = false
    setWarning(null)
    setRemaining(0)
  }, [])

  // Đếm ngược
  useEffect(() => {
    if (deadlineRef.current === null) return undefined

    const timer = setInterval(() => {
      const left = Math.ceil((deadlineRef.current - Date.now()) / 1000)

      if (left <= 0) {
        clearInterval(timer)
        deadlineRef.current = null
        setRemaining(0)
        setWarning(null)
        // Hết giờ mà không quay lại: KHÔNG cộng thêm vi phạm. Lần thoát đó đã
        // được tính ngay khi phát sinh (xem handleIncident ở ExamRoom). Cộng
        // thêm ở đây sẽ khiến ngưỡng bị "phình" nhanh và rối.
        reportedRef.current = true
        return
      }
      setRemaining(left)
    }, 250)

    return () => clearInterval(timer)
  }, [warning])

  return { warning, remaining, triggerWarning, clearWarning }
}

export default useViolationWarning
