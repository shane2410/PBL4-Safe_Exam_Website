import { useEffect } from 'react'

/**
 * Nhóm 1 — CHẶN ĐƯỢC THẬT SỰ (skills.md Quy tắc #3).
 *
 * Chặn copy/paste/cut, chuột phải, in, và các tổ hợp phím mở DevTools.
 * GHI NHẬN ĐẶC BIỆT: đây là cơ chế ngăn chặn mạnh nhất mà lớp A web có,
 * vì sự kiện thật sự đến từ trình duyệt nên `preventDefault()` có tác dụng.
 *
 * MỖI CỜ POLICY PHẢI TẮT ĐỘC LẬP.
 *
 * Trước đây hook chỉ nhận một tham số `enabled` gộp chung
 * (`block_copy_paste || block_devtools`), nên giảng viên tắt
 * `block_copy_paste` mà vẫn bật `block_devtools` thì Ctrl+C/V vẫn bị chặn và
 * vẫn bị tính lỗi COPY_PASTE_ATTEMPT. Ngược lại `disable_print` không hề được
 * truyền vào, nên Ctrl+P luôn bị chặn bất kể cấu hình.
 *
 * Lưu ý: chỉ chặn được trong phạm vi tab. Thí sinh vẫn có thể dùng phần mềm
 * chụp màn hình hoặc thiết bị khác ở tầng hệ điều hành — ngoài phạm vi kỹ thuật
 * của lớp web (xem docs/BAOCAO_LIMITATION.md, skills.md Quy tắc #5).
 */

/** Ctrl/Cmd + phím tắt liên quan sao chép nội dung. */
const COPY_PASTE_COMBINATIONS = [
  { ctrl: true, key: 'c' },
  { ctrl: true, key: 'v' },
  { ctrl: true, key: 'x' },
  { ctrl: true, key: 'a' }, // ctrl+A để chọn tất cả rồi copy
]

/** Ctrl/Cmd + phím tắt mở công cụ phát triển. */
const DEVTOOLS_COMBINATIONS = [
  { ctrl: true, shift: true, key: 'i' },
  { ctrl: true, shift: true, key: 'j' },
  { ctrl: true, shift: true, key: 'c' },
]

/** Ctrl/Cmd + phím tắt in / lưu trang / xem source. */
const PRINT_COMBINATIONS = [
  { ctrl: true, key: 'p' }, // in
  { ctrl: true, key: 's' }, // lưu trang
  { ctrl: true, key: 'u' }, // view-source
]

function matches(combo, e, key) {
  return (
    combo.ctrl === (e.ctrlKey || e.metaKey) &&
    Boolean(combo.shift) === e.shiftKey &&
    combo.key === key
  )
}

/**
 * @param {object}  options
 * @param {boolean} options.blockCopyPaste - chặn Ctrl+C/V/X/A, chuột phải, kéo thả
 * @param {boolean} options.blockDevTools  - chặn F12 và Ctrl+Shift+I/J/C
 * @param {boolean} options.disablePrint   - chặn Ctrl+P, Ctrl+S, Ctrl+U
 * @param {Function} options.logViolation  - báo vi phạm lên server
 */
export function useKeyboardBlock({
  blockCopyPaste = false,
  blockDevTools = false,
  disablePrint = false,
  logViolation,
}) {
  useEffect(() => {
    if (!blockCopyPaste && !blockDevTools && !disablePrint) return undefined

    const onKeyDown = (e) => {
      const key = (e.key || '').toLowerCase()

      if (blockDevTools) {
        if (key === 'f12') {
          e.preventDefault()
          logViolation?.('DEVTOOLS_DETECTED', { key: 'F12' })
          return
        }
        if (DEVTOOLS_COMBINATIONS.some((c) => matches(c, e, key))) {
          e.preventDefault()
          logViolation?.('DEVTOOLS_DETECTED', { key: e.key })
          return
        }
      }

      if (blockCopyPaste && COPY_PASTE_COMBINATIONS.some((c) => matches(c, e, key))) {
        e.preventDefault()
        logViolation?.('COPY_PASTE_ATTEMPT', { key: e.key })
        return
      }

      // In/lưu/xem-source chỉ CHẶN mà không ghi log — không phải hành vi gian lận.
      if (disablePrint && PRINT_COMBINATIONS.some((c) => matches(c, e, key))) {
        e.preventDefault()
      }
    }

    // Chuột phải và kéo-thả là đường lấy nội dung, nên đi theo cờ copy/paste.
    const onContextMenu = (e) => {
      if (!blockCopyPaste) return
      e.preventDefault()
      logViolation?.('RIGHT_CLICK_ATTEMPT', {})
    }

    const onDragStart = (e) => {
      if (!blockCopyPaste) return
      e.preventDefault()
    }

    document.addEventListener('keydown', onKeyDown, true)
    document.addEventListener('contextmenu', onContextMenu)
    document.addEventListener('dragstart', onDragStart)

    return () => {
      document.removeEventListener('keydown', onKeyDown, true)
      document.removeEventListener('contextmenu', onContextMenu)
      document.removeEventListener('dragstart', onDragStart)
    }
  }, [blockCopyPaste, blockDevTools, disablePrint, logViolation])

  return {}
}

export default useKeyboardBlock
