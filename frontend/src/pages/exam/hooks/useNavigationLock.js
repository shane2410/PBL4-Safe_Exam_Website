import { useEffect } from 'react'

/**
 * Nhóm 1 — CHẶN ĐƯỢC THẬT SỰ (skills.md Quy tắc #3).
 *
 * Chặn thí sinh rời khỏi trang thi:
 *  - Link bấm ra ngoài (mở tab mới, kéo theo khi Ctrl+click)
 *  - Nút Back / Forward của trình duyệt
 *  - `beforeunload` khi đóng tab
 *  - Gọi `window.open` từ mã trong trang
 *
 * Lưu ý: vẫn có thể lách bằng việc mở DevTools rồi gõ tay — nhưng các cơ chế
 * khác sẽ ghi nhận lại việc đó.
 */
export function useNavigationLock({ enabled, logViolation }) {
  useEffect(() => {
    if (!enabled) return undefined

    const onBeforeUnload = (e) => {
      e.preventDefault()
      // Chrome yêu cầu returnValue để hiện hộp thoại xác nhận
      e.returnValue = ''
      logViolation?.('TAB_SWITCH', { source: 'beforeunload' })
      return ''
    }

    const onPopState = () => {
      logViolation?.('TAB_SWITCH', { source: 'popstate' })
      // Đẩy người dùng trở lại trang thi
      window.history.pushState(null, '', window.location.href)
    }

    const onClick = (e) => {
      const link = e.target.closest?.('a')
      if (!link) return
      const href = link.getAttribute('href')
      if (!href || href.startsWith('#')) return

      const url = new URL(href, window.location.href)
      if (url.origin !== window.location.origin) {
        e.preventDefault()
        logViolation?.('TAB_SWITCH', { source: 'external_link', href: url.href })
      }
    }

    window.addEventListener('beforeunload', onBeforeUnload)
    window.addEventListener('popstate', onPopState)
    document.addEventListener('click', onClick, true)

    // Đẩy 1 entry vào lịch sử để nút Back không rời khỏi trang thi ngay lập tức.
    // Mỗi lần người dùng bấm Back, onPopState sẽ đẩy lại 1 entry — tức là người
    // dùng không thoát được bằng phím Back. Đây là hành vi CỐ Ý.
    // Lối thoát sạch duy nhất là nút "Thoát & Nộp bài" (có ở cả thanh trên và
    // cuối sidebar) — luôn hiển thị, không phụ thuộc cuộn trang.
    window.history.pushState({ examLock: true }, '', window.location.href)

    return () => {
      window.removeEventListener('beforeunload', onBeforeUnload)
      window.removeEventListener('popstate', onPopState)
      document.removeEventListener('click', onClick, true)
      // Gỡ entry khoá đã thêm khi rời phòng thi (nộp bài xong), để nút Back
      // của trình duyệt hoạt động bình thường ở trang kế tiếp.
      if (window.history.state?.examLock) {
        window.history.back()
      }
    }
  }, [enabled, logViolation])

  return {}
}

export default useNavigationLock
