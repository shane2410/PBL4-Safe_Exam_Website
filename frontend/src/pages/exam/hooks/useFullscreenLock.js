import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Nhóm 1 — CHẶN ĐƯỢC THẬT SỰ (skills.md Quy tắc #3).
 *
 * Bắt fullscreen khi bắt đầu thi và ghi nhận khi thí sinh thoát ra.
 *
 * LƯU Ý QUAN TRỌNG: hầu hết trình duyệt CHỈ cho phép gọi `requestFullscreen()`
 * trong một sự kiện do người dùng kích hoạt (click/phím). Vì vậy phải có một
 * nút "Bắt đầu thi" riêng — không thể tự động vào fullscreen ngay khi trang mở.
 *
 * Thoát fullscreen bằng Esc/F11 là HỆ ĐIỀU HÀNH xử lý — ta chỉ PHÁT HIỆN được
 * việc đã xảy ra, không chặn được hành động.
 */
export function useFullscreenLock({ enabled, onExit }) {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const exitReportedRef = useRef(false)
  // Đã TỪNG vào fullscreen hay chưa. Cần để phân biệt "thoát fullscreen" với
  // "chưa bao giờ vào được fullscreen" — hai việc khác nhau hoàn toàn.
  const wasFullscreenRef = useRef(false)

  const requestFullscreen = useCallback(async () => {
    // KHÔNG được kiểm tra `enabled` ở đây.
    //
    // `enabled` = inProgress && policy.require_fullscreen, mà inProgress phụ thuộc
    // `started`. Tại thời điểm người dùng bấm "Bắt đầu thi", `setStarted(true)`
    // chưa được React áp dụng nên closure vẫn giữ `enabled = false` -> hàm return
    // ngay lập tức và fullscreen KHÔNG BAO GIỜ được bật. (Đã xảy ra 1 lần:
    // thí sinh bấm nút, không có gì xảy ra, nhưng hệ thống lại ghi nhận vi phạm.)
    //
    // `enabled` chỉ dùng để bật/tắt phần GIÁM SÁT bên dưới, không điều khiển
    // hành động thủ công này. Việc gọi vẫn an toàn vì chỉ nút "Bắt đầu thi" gọi tới.
    if (typeof document === 'undefined' || document.fullscreenElement) return true
    try {
      await document.documentElement.requestFullscreen()
      return Boolean(document.fullscreenElement)
    } catch {
      // Trình duyệt từ chối (không có user gesture, hoặc chính sách trình duyệt).
      return false
    }
  }, [])

  const exitFullscreen = useCallback(async () => {
    if (!document.fullscreenElement) return
    try {
      await document.exitFullscreen()
    } catch {
      /* bỏ qua */
    }
  }, [])

  // Giữ callback trong ref để effect bên dưới KHÔNG phải phụ thuộc vào nó.
  //
  // Đây là điểm cực kỳ dễ sai: nếu để `onExit` trong deps của effect giám sát,
  // mà caller truyền arrow function inline (rất phổ biến), thì effect sẽ
  // chạy lại ở MỌI lần component render. Mà cleanup của effect lại gọi
  // exitFullscreen() -> chỉ cần thí sinh trả lời một câu (state đổi -> render
  // lại) là trình duyệt bật fullscreen, rồi thoát fullscreen, rồi ghi nhận
  // vi phạm. Toàn bộ cơ chế khoá trở nên vô dụng. (Đã dính lỗi này 1 lần.)
  const onExitRef = useRef(onExit)
  onExitRef.current = onExit

  // --- Giám sát ---
  // Chỉ phụ thuộc `enabled`. Khi `enabled` đổi thì mới bắt đầu/không theo dõi.
  useEffect(() => {
    if (!enabled) return undefined

    const onChange = () => {
      const active = Boolean(document.fullscreenElement)
      setIsFullscreen(active)

      if (active) {
        wasFullscreenRef.current = true
        exitReportedRef.current = false
        return
      }

      // Chỉ coi là "THOÁT" khi thí sinh ĐÃ vào fullscreen trước đó.
      // Nếu ta chưa từng vào được (trình duyệt từ chối, thiết bị không hỗ trợ)
      // thì việc "không có fullscreenElement" là trạng thái bình thường —
      // không được ghi nhận là thí sinh cố ý thoát.
      if (!wasFullscreenRef.current) return

      if (!exitReportedRef.current) {
        exitReportedRef.current = true
        // Không tự ghi vi phạm ở đây. Việc đếm vi phạm do ExamRoom quản lý
        // một chỗ (handleIncident) để một hành động rời đi chỉ bị tính MỘT lần.
        onExitRef.current?.()
      }
    }

    document.addEventListener('fullscreenchange', onChange)
    // Đồng bộ trạng thái ban đầu nếu thí sinh vào lại giữa chừng
    onChange()

    return () => {
      document.removeEventListener('fullscreenchange', onChange)
    }
  }, [enabled])

  // --- Tắt fullscreen khi RỜI phòng thi ---
  // Effect riêng, chỉ chạy khi component bị gỡ (nộp bài xong / điều hướng đi nơi
  // khác). Tách riêng để không gắn việc tắt fullscreen vào cleanup của effect
  // giám sát — nếu gộp, mỗi lần `enabled` đổi cũng tắt fullscreen oan.
  useEffect(
    () => () => {
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {})
      }
    },
    [],
  )

  return { isFullscreen, requestFullscreen, exitFullscreen }
}

export default useFullscreenLock
