import { useCallback, useEffect, useMemo, useRef } from 'react'
import { getSocket } from '../../../services/socketClient'
import policyService from '../../../services/policyService'

/**
 * Hook gốc cho toàn bộ cơ chế khoá an toàn.
 *
 * Đây là nguồn duy nhất cấp `policy` cho các hook con (skills.md Quy tắc #3 & #6):
 * UI không tự quyết định bật/tắt cơ chế, mọi thứ đều đọc từ policy do SERVER cấp.
 * Tắt cờ trong DB là thực sự tắt, không phải chỉ tắt nhãn.
 *
 * @param {object}  examState - Response của POST /exam-sessions/join
 * @param {Function} onForceSubmit - Server yêu cầu khoá phiên và nộp bài
 */
export function useSecurityPolicy(examState, onForceSubmit) {
  // KHÔNG dùng useState cho các giá trị phụ thuộc `examState`.
  //
  // Hook này chạy lần đầu khi ExamRoom còn đang join (examState === null).
  // `useState(initial)` chỉ dùng initial ở lần render ĐẦU TIÊN, nên trước đây
  // cả policy lẫn 2 cờ bị kẹt vĩnh viễn ở giá trị mặc định: cấu hình riêng
  // của đề bị phớt lờ và PolicyGate ("chỉ cho phép SEB") không bao giờ hiện.
  // useMemo/giá trị dẫn xuất thì luôn theo kịp examState mới.
  const policy = useMemo(
    () => policyService.normalize(examState?.security_policy),
    [examState?.security_policy],
  )
  const requireSafeBrowser = Boolean(examState?.require_safe_browser)
  const restrictedMode = Boolean(examState?.restricted_mode)

  const socketRef = useRef(null)
  const forceSubmitRef = useRef(onForceSubmit)
  forceSubmitRef.current = onForceSubmit

  // Khi trang này chạy BÊN TRONG SEB Client, chính SEB Client đã giữ socket
  // và tự gửi heartbeat. Nếu trang web lại tự mở socket thì server thấy 2
  // kết nối cho cùng một phiên và ghi DUPLICATE_LOGIN rồi buộc nộp bài — tức
  // là dùng đúng SEB Client thì lại bị phạt. Vì vậy khi `embedded=1`, trang
  // nhường socket hoàn toàn cho client bọc nó.
  const embeddedInSeb = useMemo(
    () => new URLSearchParams(window.location.search).get('embedded') === '1',
    [],
  )

  // --- Kết nối socket, subscribe phòng thi ---
  useEffect(() => {
    if (!examState?.session_token || !examState?.room_code) return undefined
    if (embeddedInSeb) return undefined

    const socket = getSocket()
    socketRef.current = socket

    socket.on('connect', () => {
      socket.emit('join_exam_room', {
        room_code: examState.room_code,
        session_token: examState.session_token,
      })
    })

    socket.on('force_submit', (payload) => {
      forceSubmitRef.current?.(payload)
    })

    if (socket.connected) {
      socket.emit('join_exam_room', {
        room_code: examState.room_code,
        session_token: examState.session_token,
      })
    }

    return () => {
      socket.off('connect')
      socket.off('force_submit')
    }
  }, [examState?.session_token, examState?.room_code, embeddedInSeb])

  // --- Heartbeat định kỳ: server giữ đồng hồ chuẩn (Quy tắc #4.1) ---
  useEffect(() => {
    const socket = socketRef.current
    if (!socket) return undefined

    const timer = setInterval(() => {
      if (socket.connected) socket.emit('heartbeat', {})
    }, 10000)

    return () => clearInterval(timer)
  }, [examState?.session_token])

  /**
   * Gửi vi phạm lên server. Server TỰ quyết định severity và ngưỡng xử lý —
   * client không được tự quyết định mức nghiêm trọng hay có nộp bài hay không.
   */
  const logViolation = useCallback(
    (type, detail = {}) => {
      const socket = socketRef.current
      if (!socket || !socket.connected) {
        // Khi nhúng trong SEB Client, việc báo vi phạm do CHÍNH SEB Client đảm
        // nhiệm (nó chặn ở tầng hệ đối hành, mạnh hơn các hook trong trang).
        // Hook ở đây chỉ bắt được sự kiện trong DOM — nếu cũng báo, cùng một
        // hành vi sẽ bị đếm hai lần và làm sai ngưỡng trên dashboard.
        return
      }
      socket.emit('violation', {
        type,
        detail,
        // Timestamp phía client chỉ để đối chiếu, server tự ghi server_timestamp
        clientTimestamp: new Date().toISOString(),
      })
    },
    [],
  )

  return {
    policy,
    requireSafeBrowser,
    restrictedMode,
    logViolation,
  }
}

export default useSecurityPolicy
