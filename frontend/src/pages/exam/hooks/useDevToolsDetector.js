import { useEffect, useRef } from 'react'

/**
 * Nhóm 2 — CHỈ PHÁT HIỆN ĐƯỢC (skills.md Quy tắc #3).
 *
 * Heuristic phổ biến: khi DevTools mở dạng docked, kích thước cửa sổ ngoài
 * (`outerWidth/outerHeight`) lớn hơn vùng nội dung (`innerWidth/innerHeight`).
 *
 * GIỚI HẠN PHẢI NÊU RÕ TRONG BÁO CÁO (Quy tắc #5):
 *  - DevTools mở dạng CỬA SỔ TÁCH RỜI (undocked) sẽ KHÔNG bị phát hiện.
 *  - Có thể báo nhầm (false positive) khi người dùng thu nhỏ/phóng to cửa sổ
 *    hoặc đổi tỉ lệ zoom của hệ điều hành.
 *  - Vì vậy ta dùng ngưỡng TRƯỚC nghiêng (threshold) thay vì so khác tuyệt đối,
 *    và chỉ ghi log sau khi điều kiện kéo dài liên tục để giảm báo nhầm.
 */
const SIZE_THRESHOLD_PX = 160
const PERSISTENCE_MS = 900
const POLL_INTERVAL_MS = 500

export function useDevToolsDetector({ enabled, logViolation }) {
  const firstDetectionAtRef = useRef(null)

  useEffect(() => {
    if (!enabled) return undefined

    const timer = setInterval(() => {
      const widthGap = window.outerWidth - window.innerWidth
      const heightGap = window.outerHeight - window.innerHeight

      const looksOpen = widthGap > SIZE_THRESHOLD_PX || heightGap > SIZE_THRESHOLD_PX

      if (looksOpen) {
        // Phải giữ nguyên điều kiện trong khoảng thời gian đủ dài mới ghi log
        if (firstDetectionAtRef.current === null) {
          firstDetectionAtRef.current = Date.now()
          return
        }
        if (Date.now() - firstDetectionAtRef.current >= PERSISTENCE_MS) {
          firstDetectionAtRef.current = Date.now()
          logViolation?.('DEVTOOLS_DETECTED', {
            method: 'window_size_heuristic',
            width_gap: widthGap,
            height_gap: heightGap,
          })
        }
      } else {
        firstDetectionAtRef.current = null
      }
    }, POLL_INTERVAL_MS)

    return () => clearInterval(timer)
  }, [enabled, logViolation])

  return {}
}

export default useDevToolsDetector
