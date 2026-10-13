import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Modal from '../../components/common/Modal'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import teacherService from '../../services/teacherService'
import { getSocket } from '../../services/socketClient'
import { extractErrorMessage } from '../../services/apiClient'
import {
  VIOLATION_LABELS,
  SESSION_STATUS,
  riskBarColor,
  formatDateTime,
} from '../../utils/labels'

/**
 * Dashboard giám sát thời gian thực (Teacher/QTV).
 *
 * Nguồn dữ liệu:
 *  - `join_monitor_room` trả về danh sách thí sinh đang kết nối.
 *  - Server đẩy `student_status_change` và `violation_alert` vào phòng `monitor_<ROOM>`.
 *
 * Lưu ý giới hạn (skills.md Quy tắc #5): các sự kiện này là **ghi nhận bằng chứng**,
 * không phải ngăn chặn. Thời gian hiển thị là lúc client gửi lên, đã đối chiếu với
 * mốc server.
 */
export default function MonitorDashboard() {
  const { scheduleId } = useParams()
  const [searchParams] = useSearchParams()
  const roomCode = (searchParams.get('room') || '').toUpperCase()

  const [students, setStudents] = useState([])
  const [events, setEvents] = useState([])
  const [connected, setConnected] = useState(false)
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [forcing, setForcing] = useState(null)

  const socketRef = useRef(null)

  // Kéo số liệu tổng quan từ API báo cáo (bổ sung cho dữ liệu realtime)
  const loadStats = useCallback(async () => {
    if (!scheduleId) return
    try {
      const data = await teacherService.getScheduleStatistics(scheduleId)
      setStats(data)
      setStudents((prev) => {
        if (prev.length === 0) {
          return data.candidates.map((c) => ({
            session_id: c.session_id,
            student_name: c.student_name,
            student_code: c.student_code,
            status: c.status,
            risk_score: c.risk_score,
            tab_switch_count: c.tab_switch_count,
            fullscreen_exit_count: c.fullscreen_exit_count,
            submitted_at: c.submitted_at,
          }))
        }
        // Giữ dữ liệu realtime, chỉ bổ sung trường còn thiếu
        return prev.map((s) => {
          const found = data.candidates.find((c) => c.session_id === s.session_id)
          return found ? { ...s, risk_score: Math.max(s.risk_score ?? 0, found.risk_score) } : s
        })
      })
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được số liệu ca thi.'))
    }
  }, [scheduleId])

  useEffect(() => {
    loadStats()
  }, [loadStats])

  // Kết nối Socket.IO vào phòng giám sát
  useEffect(() => {
    if (!roomCode) return undefined

    const socket = getSocket()
    socketRef.current = socket

    const onConnect = () => {
      setConnected(true)
      socket.emit('join_monitor_room', { room_code: roomCode }, (res) => {
        if (res?.active_students) {
          setStudents(
            res.active_students.map((s) => ({
              session_id: s.session_id,
              student_name: s.student_name,
              student_code: s.student_code,
              status: 'IN_PROGRESS',
              risk_score: s.risk_score ?? 0,
              tab_switch_count: s.tab_switch_count ?? 0,
              fullscreen_exit_count: s.fullscreen_exit_count ?? 0,
              submitted_at: null,
            })),
          )
        }
      })
    }

    const onDisconnect = () => setConnected(false)

    const onStatusChange = (payload) => {
      setStudents((prev) => {
        const idx = prev.findIndex((s) => s.session_id === payload.session_id)
        const entry = {
          session_id: payload.session_id,
          student_name: payload.student_name,
          student_code: payload.student_code,
          status: payload.status === 'ONLINE' ? 'IN_PROGRESS' : 'DISCONNECTED',
          risk_score: payload.risk_score ?? 0,
          tab_switch_count: payload.tab_switch_count ?? 0,
          fullscreen_exit_count: payload.fullscreen_exit_count ?? 0,
          submitted_at: null,
        }
        if (idx === -1) return [...prev, entry]
        const next = [...prev]
        next[idx] = { ...next[idx], ...entry, student_name: next[idx].student_name || entry.student_name }
        return next
      })

      setEvents((prev) =>
        [
          {
            id: `${payload.session_id}-${payload.status}-${Date.now()}`,
            session_id: payload.session_id,
            student_name: payload.student_name,
            type: payload.status === 'ONLINE' ? 'VÀO PHÒNG' : 'RỜI PHÒNG',
            timestamp: payload.timestamp,
            tone: payload.status === 'ONLINE' ? 'success' : 'warning',
          },
          ...prev,
        ].slice(0, 30),
      )
    }

    const onViolation = (payload) => {
      setStudents((prev) =>
        prev.map((s) =>
          s.session_id === payload.session_id
            ? {
                ...s,
                risk_score: payload.risk_score ?? s.risk_score,
                tab_switch_count: payload.tab_switch_count ?? s.tab_switch_count,
                fullscreen_exit_count: payload.fullscreen_exit_count ?? s.fullscreen_exit_count,
              }
            : s,
        ),
      )
      setEvents((prev) =>
        [
          {
            id: `${payload.session_id}-${payload.event_type}-${Date.now()}`,
            session_id: payload.session_id,
            student_name: payload.student_name,
            type: VIOLATION_LABELS[payload.event_type] || payload.event_type,
            detail: payload.detail,
            timestamp: payload.timestamp,
            tone: 'error',
          },
          ...prev,
        ].slice(0, 30),
      )
    }

    const onForceSubmitted = (payload) => {
      setEvents((prev) =>
        [
          {
            id: `force-${Date.now()}`,
            session_id: payload.session_id,
            student_name: payload.student_name,
            type: `THU BÀI: ${payload.reason}`,
            timestamp: new Date().toISOString(),
            tone: 'error',
          },
          ...prev,
        ].slice(0, 30),
      )
      loadStats()
    }

    socket.on('connect', onConnect)
    socket.on('disconnect', onDisconnect)
    socket.on('student_status_change', onStatusChange)
    socket.on('violation_alert', onViolation)
    socket.on('student_force_submitted', onForceSubmitted)

    if (socket.connected) onConnect()

    return () => {
      socket.off('connect', onConnect)
      socket.off('disconnect', onDisconnect)
      socket.off('student_status_change', onStatusChange)
      socket.off('violation_alert', onViolation)
      socket.off('student_force_submitted', onForceSubmitted)
    }
  }, [roomCode, loadStats])

  const forceSubmit = (student) => {
    const socket = socketRef.current
    if (!socket) return
    socket.emit(
      'teacher_force_submit',
      { session_id: student.session_id, reason: 'Giám thị thu bài do phát hiện gian lận' },
      (res) => {
        if (res?.status === 'success') {
          setForcing(null)
          loadStats()
        } else {
          setError(res?.message || 'Không thu được bài.')
        }
      },
    )
  }

  const online = students.filter((s) => s.status === 'IN_PROGRESS').length
  const submitted = students.filter((s) => s.status === 'SUBMITTED').length
  const alertCount = events.filter((e) => e.tone === 'error').length

  const statCards = [
    { label: 'Tổng thí sinh', value: stats?.total_candidates ?? students.length },
    { label: 'Đang làm bài', value: online, tone: 'success' },
    { label: 'Đã nộp bài', value: submitted, tone: 'primary' },
    { label: 'Sự cảnh báo', value: alertCount, tone: 'warning' },
  ]

  if (!roomCode) {
    return (
      <div className="p-8">
        <Alert variant="warning">
          Thiếu mã phòng trong địa chỉ. Hãy mở từ danh sách Lịch thi.
        </Alert>
      </div>
    )
  }

  return (
    <div className="p-8 bg-slate-100 min-h-screen">
      {/* Thanh tiêu đề tối */}
      <div className="bg-navy text-white rounded-lg px-5 py-4 flex items-center justify-between mb-6">
        <div className="flex items-center gap-3 min-w-0">
          <Icon name="monitoring" size={22} />
          <div className="min-w-0">
            <h1 className="font-headline-sm font-semibold truncate">
              Giám sát phòng {roomCode}
            </h1>
            <p className="text-xs text-slate-400 truncate">{stats?.exam_title || 'Đang tải…'}</p>
          </div>
        </div>
        <Badge tone={connected ? 'success' : 'error'} icon={connected ? 'check_circle' : 'cancel'}>
          {connected ? 'Đang trực tuyến' : 'Mất kết nối'}
        </Badge>
      </div>

      <div className="max-w-6xl mx-auto space-y-6 pb-12">
        {error && <Alert variant="error">{error}</Alert>}

        <Alert variant="warning">
          <strong>Lưu ý:</strong> mọi hành động “Thu bài” sẽ được ghi vào nhật ký phục
          tra kèm lý do. Dữ liệu hiển thị là bằng chứng ghi nhận, không phải cơ chế
          ngăn chặn gian lận.
        </Alert>

        {/* Thẻ số liệu */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((c) => (
            <div key={c.label} className="card p-5">
              <p className="text-sm text-slate-500">{c.label}</p>
              <p
                className={`text-2xl font-bold mt-1 ${
                  c.tone === 'success'
                    ? 'text-success'
                    : c.tone === 'warning'
                      ? 'text-warning'
                      : c.tone === 'primary'
                        ? 'text-primary'
                        : 'text-slate-900'
                }`}
              >
                {c.value}
              </p>
            </div>
          ))}
        </div>

        {/* Bảng thí sinh */}
        <Card
          icon="group"
          title="Thí sinh trong phòng"
          action={
            <button type="button" onClick={loadStats} className="btn-ghost btn-sm">
              <Icon name="refresh" size={16} />
              Làm mới
            </button>
          }
        >
          {students.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Icon name="group" size={32} className="text-slate-300 mx-auto" />
              <p className="mt-3">Chưa có thí sinh nào kết nối vào phòng.</p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md">Mã SV</th>
                    <th className="px-6 py-3 font-label-md">Họ và tên</th>
                    <th className="px-6 py-3 font-label-md">Trạng thái</th>
                    <th className="px-6 py-3 font-label-md">Rủi ro</th>
                    <th className="px-6 py-3 font-label-md text-center">Chuyển tab</th>
                    <th className="px-6 py-3 font-label-md text-center">Thoát FS</th>
                    <th className="px-6 py-3 font-label-md">Nộp lúc</th>
                    <th className="px-6 py-3 font-label-md text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {students.map((s) => {
                    const st = SESSION_STATUS[s.status] || SESSION_STATUS.IN_PROGRESS
                    return (
                      <tr key={s.session_id} className="hover:bg-slate-50">
                        <td className="px-6 py-3 font-mono text-xs text-slate-600">
                          {s.student_code || '—'}
                        </td>
                        <td className="px-6 py-3 text-slate-800">{s.student_name}</td>
                        <td className="px-6 py-3">
                          <Badge tone={st.tone}>{st.label}</Badge>
                        </td>
                        <td className="px-6 py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-2 rounded-full bg-slate-200 overflow-hidden">
                              <div
                                className={`h-full ${riskBarColor(s.risk_score ?? 0)}`}
                                style={{ width: `${Math.min(100, Math.round((s.risk_score ?? 0) / 3))}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium text-slate-600 tabular-nums">
                              {s.risk_score ?? 0}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-3 text-center text-slate-600">
                          {s.tab_switch_count ?? 0}
                        </td>
                        <td className="px-6 py-3 text-center text-slate-600">
                          {s.fullscreen_exit_count ?? 0}
                        </td>
                        <td className="px-6 py-3 text-slate-500 text-xs">
                          {s.submitted_at ? formatDateTime(s.submitted_at) : '—'}
                        </td>
                        <td className="px-6 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => setForcing(s)}
                            disabled={s.status === 'SUBMITTED'}
                            className="btn-danger-outline btn-sm"
                          >
                            <Icon name="lock" size={14} />
                            Thu bài
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Dòng sự kiện */}
        <Card icon="history" title="Sự kiện gần đây">
          {events.length === 0 ? (
            <p className="text-center text-slate-500 py-8">
              Chưa có sự kiện nào. Dữ liệu sẽ hiện ở đây khi thí sinh vào phòng hoặc
              có hành vi vi phạm.
            </p>
          ) : (
            <ol className="space-y-3">
              {events.map((e) => (
                <li key={e.id} className="flex gap-3 items-start">
                  <span
                    className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                      e.tone === 'error'
                        ? 'bg-error'
                        : e.tone === 'success'
                          ? 'bg-success'
                          : 'bg-warning'
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-slate-800">
                      <span className="font-medium">{e.student_name}</span> — {e.type}
                    </p>
                    <p className="text-xs text-slate-400">
                      {e.session_id ? `Phiên #${e.session_id} · ` : ''}
                      {formatDateTime(e.timestamp)}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      {/* Xác nhận thu bài */}
      <Modal
        open={Boolean(forcing)}
        onClose={() => setForcing(null)}
        title="Xác nhận thu bài"
        footer={
          <>
            <button type="button" onClick={() => setForcing(null)} className="btn-ghost">
              Huỷ
            </button>
            <button type="button" onClick={() => forceSubmit(forcing)} className="btn-danger">
              Thu bài ngay
            </button>
          </>
        }
      >
        <p className="text-slate-700">
          Thu bài của thí sinh <strong>{forcing?.student_name}</strong> (
          {forcing?.student_code || '—'})?
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Bài sẽ được chấm điểm ngay và ghi vào nhật ký phục tra kèm lý do do giám thị
          cung cấp. Thí sinh không thể làm lại.
        </p>
      </Modal>
    </div>
  )
}
