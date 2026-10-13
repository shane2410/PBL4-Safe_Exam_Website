import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Select from '../../components/common/Select'
import Modal from '../../components/common/Modal'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import teacherService from '../../services/teacherService'
import { extractErrorMessage } from '../../services/apiClient'
import {
  VIOLATION_LABELS,
  SEVERITY_TONES,
  SESSION_STATUS,
  riskTone,
  riskBarColor,
  formatDateTime,
} from '../../utils/labels'

/** Thanh điểm rủi ro — màu theo ngưỡng, thanh bám theo MAX_RISK_SCORE = 1000. */
function RiskBar({ score }) {
  const pct = Math.min(100, Math.round((score / 300) * 100))
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 rounded-full bg-slate-200 overflow-hidden flex-shrink-0">
        <div className={`h-full ${riskBarColor(score)}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-slate-600 tabular-nums w-8">{score}</span>
    </div>
  )
}

/** Báo cáo kết quả thi theo ca (Teacher). */
export default function Reports() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [schedules, setSchedules] = useState([])
  const [scheduleId, setScheduleId] = useState(searchParams.get('schedule') || '')
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState('')

  const [violations, setViolations] = useState(null)
  const [violationLoading, setViolationLoading] = useState(false)

  useEffect(() => {
    teacherService
      .getSchedules()
      .then((list) => {
        setSchedules(list)
        if (!scheduleId && list.length > 0) setScheduleId(String(list[0].id))
      })
      .catch(() => setError('Không tải được danh sách ca thi.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadStats = useCallback(async () => {
    if (!scheduleId) {
      setStats(null)
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await teacherService.getScheduleStatistics(scheduleId)
      setStats(data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được báo cáo.'))
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [scheduleId])

  useEffect(() => {
    loadStats()
  }, [loadStats])

  const changeSchedule = (value) => {
    setScheduleId(value)
    setSearchParams(value ? { schedule: value } : {})
  }

  const download = async (format) => {
    setDownloading(format)
    setError('')
    try {
      await teacherService.downloadReport(scheduleId, format)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được báo cáo.'))
    } finally {
      setDownloading('')
    }
  }

  const openViolations = async (sessionId) => {
    setViolationLoading(true)
    setViolations({ sessionId, items: [] })
    try {
      const items = await teacherService.getSessionViolations(sessionId)
      setViolations({ sessionId, items })
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được nhật ký vi phạm.'))
      setViolations(null)
    } finally {
      setViolationLoading(false)
    }
  }

  const statCards = stats
    ? [
        { label: 'Điểm trung bình', value: stats.average_score, tone: 'primary' },
        { label: 'Điểm cao nhất', value: stats.highest_score, tone: 'success' },
        { label: 'Điểm thấp nhất', value: stats.lowest_score, tone: 'error' },
        {
          label: 'Tỉ lệ nộp bài',
          value:
            stats.total_candidates > 0
              ? `${Math.round((stats.submitted_count / stats.total_candidates) * 100)}%`
              : '0%',
          tone: 'warning',
        },
      ]
    : []

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="space-y-1">
          <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
            Báo cáo kết quả thi
          </h1>
          <p className="text-slate-600">
            Thống kê điểm, điểm rủi ro và xuất báo cáo theo từng ca thi.
          </p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        {/* Chọn ca + xuất file */}
        <div className="flex flex-wrap gap-3 items-end">
          <Select
            label="Phòng thi"
            value={scheduleId}
            onChange={changeSchedule}
            options={[
              { value: '', label: 'Chọn phòng thi…' },
              ...schedules.map((s) => ({ value: s.id, label: `${s.room_code} — ${s.exam_title}` })),
            ]}
            className="flex-1 min-w-[280px]"
          />
          <button
            type="button"
            onClick={() => download('excel')}
            disabled={!scheduleId || downloading === 'excel'}
            className="btn-outline"
          >
            <Icon name="download" size={18} />
            {downloading === 'excel' ? 'Đang tải…' : 'Xuất Excel'}
          </button>
          <button
            type="button"
            onClick={() => download('pdf')}
            disabled={!scheduleId || downloading === 'pdf'}
            className="btn-outline"
          >
            <Icon name="picture_as_pdf" size={18} />
            {downloading === 'pdf' ? 'Đang tải…' : 'Xuất PDF'}
          </button>
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-slate-500 justify-center py-8">
            <Icon name="refresh" size={20} />
            Đang tải báo cáo…
          </div>
        )}

        {stats && !loading && (
          <>
            {/* Thẻ số liệu */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {statCards.map((c) => (
                <div key={c.label} className="card p-5">
                  <p className="text-sm text-slate-500">{c.label}</p>
                  <p
                    className={`text-2xl font-bold mt-1 ${
                      c.tone === 'error'
                        ? 'text-error'
                        : c.tone === 'success'
                          ? 'text-success'
                          : c.tone === 'warning'
                            ? 'text-warning'
                            : 'text-slate-900'
                    }`}
                  >
                    {c.value}
                  </p>
                </div>
              ))}
            </div>

            {/* Bảng kết quả */}
            <Card
              icon="people_alt"
              title={`Kết quả — ${stats.room_code}`}
              action={
                <span className="text-xs text-slate-500">
                  {stats.submitted_count}/{stats.total_candidates} đã nộp ·{' '}
                  {stats.in_progress_count} đang làm
                </span>
              }
            >
              {stats.candidates.length === 0 ? (
                <p className="text-center text-slate-500 py-10">
                  Chưa có thí sinh nào vào phòng thi này.
                </p>
              ) : (
                <div className="overflow-x-auto -mx-6 -mt-2">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-slate-500">
                        <th className="px-6 py-3 font-label-md text-center">#</th>
                        <th className="px-6 py-3 font-label-md">Mã SV</th>
                        <th className="px-6 py-3 font-label-md">Họ và tên</th>
                        <th className="px-6 py-3 font-label-md text-center">Điểm</th>
                        <th className="px-6 py-3 font-label-md">Rủi ro</th>
                        <th className="px-6 py-3 font-label-md text-center">Chuyển tab</th>
                        <th className="px-6 py-3 font-label-md text-center">Thoất FS</th>
                        <th className="px-6 py-3 font-label-md text-center">Vi phạm</th>
                        <th className="px-6 py-3 font-label-md">Trạng thái</th>
                        <th className="px-6 py-3 font-label-md">Thời gian nộp</th>
                        <th className="px-6 py-3 font-label-md" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {stats.candidates.map((c, i) => {
                        const st = SESSION_STATUS[c.status] || SESSION_STATUS.IN_PROGRESS
                        const passed = c.final_score !== null && c.final_score >= 5
                        return (
                          <tr key={c.session_id} className="hover:bg-slate-50">
                            <td className="px-6 py-3 text-center text-slate-400">{i + 1}</td>
                            <td className="px-6 py-3 font-mono text-xs text-slate-600">
                              {c.student_code || '—'}
                            </td>
                            <td className="px-6 py-3 text-slate-800">{c.student_name}</td>
                            <td className="px-6 py-3 text-center">
                              <span
                                className={`font-semibold ${
                                  c.final_score === null
                                    ? 'text-slate-400'
                                    : passed
                                      ? 'text-success'
                                      : 'text-error'
                                }`}
                              >
                                {c.final_score ?? '—'}
                              </span>
                              <span className="text-slate-400 text-xs"> / {c.total_score}</span>
                            </td>
                            <td className="px-6 py-3">
                              <RiskBar score={c.risk_score} />
                            </td>
                            <td className="px-6 py-3 text-center text-slate-600">
                              {c.tab_switch_count}
                            </td>
                            <td className="px-6 py-3 text-center text-slate-600">
                              {c.fullscreen_exit_count}
                            </td>
                            <td className="px-6 py-3 text-center">
                              {c.violation_count > 0 ? (
                                <Badge tone={riskTone(c.risk_score)}>{c.violation_count}</Badge>
                              ) : (
                                <span className="text-slate-400">0</span>
                              )}
                            </td>
                            <td className="px-6 py-3">
                              <Badge tone={st.tone}>{st.label}</Badge>
                            </td>
                            <td className="px-6 py-3 text-slate-500 text-xs">
                              {formatDateTime(c.submitted_at)}
                            </td>
                            <td className="px-6 py-3 text-right">
                              <button
                                type="button"
                                onClick={() => openViolations(c.session_id)}
                                title="Xem nhật ký vi phạm"
                                className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                              >
                                <Icon name="visibility" size={16} />
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
          </>
        )}

        {!stats && !loading && (
          <Card>
            <div className="text-center py-12 text-slate-500">
              <Icon name="query_stats" size={32} className="text-slate-300 mx-auto" />
              <p className="mt-3">Chọn một phòng thi để xem báo cáo.</p>
            </div>
          </Card>
        )}
      </div>

      {/* Nhật ký vi phạm của một thí sinh */}
      <Modal
        open={Boolean(violations)}
        onClose={() => setViolations(null)}
        title="Nhật ký vi phạm"
        maxWidth="max-w-2xl"
      >
        {violationLoading ? (
          <div className="flex items-center gap-3 text-slate-500 justify-center py-8">
            <Icon name="refresh" size={20} />
            Đang tải…
          </div>
        ) : violations?.items.length === 0 ? (
          <div className="text-center text-slate-500 py-8">
            <Icon name="check_circle" size={28} className="text-success mx-auto" />
            <p className="mt-2">Không ghi nhận vi phạm nào.</p>
          </div>
        ) : (
          <ol className="space-y-3">
            {violations?.items.map((v) => (
              <li key={v.id} className="flex gap-3">
                <span className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-800">
                      {VIOLATION_LABELS[v.event_type] || v.event_type}
                    </span>
                    <Badge tone={SEVERITY_TONES[v.severity] || 'neutral'}>{v.severity}</Badge>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Server nhận lúc {formatDateTime(v.server_timestamp)}
                  </p>
                  {v.detail && (
                    <pre className="mt-1.5 p-2 rounded bg-slate-900 text-slate-100 text-[11px] overflow-auto max-h-24">
                      {JSON.stringify(v.detail, null, 2)}
                    </pre>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Modal>
    </div>
  )
}
