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

  return socket
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}

export default getSocket
