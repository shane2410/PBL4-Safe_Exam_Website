import { useEffect } from 'react'

/**
 * Nhóm 1 — CHẶN ĐƯỢC THẬT SỰ (skills.md Quy tắc #3).
 *
 * Chặn copy/paste/cut, chuột phải, in, và các tổ hợp phím mở DevTools.
 * GHI NHẬN ĐẶC BIỆT: đây là cơ chế ngăn chặn mạnh nhất mà lớp A web có,
 * vì sự kiện thật sự đến từ trình duyệt nên `preventDefault()` có tác dụng.
 *
 * Lưu ý: chỉ chặn được trong phạm vi tab. Thí sinh vẫn có thể dùng phần mềm
 * chụp màn hình hoặc thiết bị khác ở tầng hệ điều hành — ngoài phạm vi kỹ thuật
 * của lớp web (xem docs/BAOCAO_LIMITATION.md, skills.md Quy tắc #5).
 */
const BLOCKED_COMBINATIONS = [
  { ctrl: true, key: 'c', event: 'COPY_PASTE_ATTEMPT' },
  { ctrl: true, key: 'v', event: 'COPY_PASTE_ATTEMPT' },
  { ctrl: true, key: 'x', event: 'COPY_PASTE_ATTEMPT' },
  { ctrl: true, key: 'a', event: 'COPY_PASTE_ATTEMPT' }, // ctrl+A để chọn tất cả rồi copy
  { ctrl: true, key: 'p', event: null }, // in — chặn im lặng
  { ctrl: true, key: 's', event: null }, // lưu trang
  { ctrl: true, key: 'u', event: null }, // view-source
  { ctrl: true, shift: true, key: 'i', event: 'DEVTOOLS_DETECTED' },
  { ctrl: true, shift: true, key: 'j', event: 'DEVTOOLS_DETECTED' },
  { ctrl: true, shift: true, key: 'c', event: 'DEVTOOLS_DETECTED' },
]

export function useKeyboardBlock({ enabled, logViolation }) {
  useEffect(() => {
    if (!enabled) return undefined

    const onKeyDown = (e) => {
      const key = (e.key || '').toLowerCase()

      // F12
      if (key === 'f12') {
        e.preventDefault()
        logViolation?.('DEVTOOLS_DETECTED', { key: 'F12' })
        return
      }

      const matched = BLOCKED_COMBINATIONS.find(
        (combo) =>
          combo.ctrl === (e.ctrlKey || e.metaKey) &&
          Boolean(combo.shift) === e.shiftKey &&
          combo.key === key,
      )

      if (matched) {
        e.preventDefault()
        // Chỉ ghi log với event có ý nghĩa về gian lận; thao tác in/lưu/xem-source
        // chỉ chặn mà không ghi log để tránh làm nhiễu báo cáo vi phạm.
        if (matched.event) {
          logViolation?.(matched.event, { key: e.key })
        }
      }
    }

    const onContextMenu = (e) => {
      e.preventDefault()
      logViolation?.('RIGHT_CLICK_ATTEMPT', {})
    }

    const onDragStart = (e) => e.preventDefault()

    document.addEventListener('keydown', onKeyDown, true)
    document.addEventListener('contextmenu', onContextMenu)
    document.addEventListener('dragstart', onDragStart)

    return () => {
      document.removeEventListener('keydown', onKeyDown, true)
      document.removeEventListener('contextmenu', onContextMenu)
      document.removeEventListener('dragstart', onDragStart)
    }
  }, [enabled, logViolation])

  return {}
}

export default useKeyboardBlock
