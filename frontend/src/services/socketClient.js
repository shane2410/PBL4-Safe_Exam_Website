import { io } from 'socket.io-client'

/**
 * Socket.IO client dùng chung cho lớp A (web) và sẽ dùng lại cho lớp B (SEB Client).
 * Backend dùng `python-socketio` nên giao thức tương thích hoàn toàn.
 */
const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || window.location.origin

let socket = null

export function getSocket() {
  if (socket) return socket

  socket = io(SOCKET_URL, {
    path: '/socket.io',
    transports: ['websocket', 'polling'],
    autoConnect: false,
    withCredentials: true,
  })

  // PHẢI gọi connect() thủ công vì autoConnect đang tắt.
  //
  // Trước đây không nơi nào gọi connect(), nên socket KHÔNG BAO GIỜ kết nối.
  // Hệ quả âm thầm rất đáng sợ:
  //   - useSecurityPolicy.logViolation() thấy socket.connected === false nên
  //     bỏ qua im lặng -> vi phạm của học sinh không bao giờ tới server
  //     -> bảng violation_logs rỗng -> màn hình giám sát không có gì cả,
  //     trong khi học sinh VẪN thấy cửa sổ cảnh báo (vì nó là state cục bộ).
  //   - Giáo viên vào phòng giám sát cũng không vào được phòng
  //     `monitor_<ROOM>` nên không nhận violation_alert.
  // Triệu chứng: "báo bên học sinh mà không báo bên giám sát".
  socket.connect()

  return socket
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}

export default getSocket
