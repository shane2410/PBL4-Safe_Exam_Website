import { useCallback, useEffect, useState } from 'react'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Select from '../../components/common/Select'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import apiClient, { extractErrorMessage } from '../../services/apiClient'
import { formatDateTime } from '../../utils/labels'

/** Màu badge theo nhóm thao tác — để nhật ký dễ quét bằng mắt. */
const ACTION_TONE = {
  EXAM_DELETE: 'error',
  USER_DELETE: 'error',
  PASSWORD_RESET: 'error',
  TOGGLE_REQUIRE_SAFE_BROWSER: 'warning',
  UPDATE_SECURITY_CONFIG: 'warning',
  UPDATE_SYSTEM_CONFIG: 'warning',
  USER_CREATE: 'success',
  EXAM_CREATE: 'success',
  SCHEDULE_CREATE: 'success',
}

const PAGE_SIZE = 50

/** Nhật ký thao tác quản trị (Admin). */
export default function AuditLog() {
  const [logs, setLogs] = useState([])
  const [actions, setActions] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    apiClient
      .get('/admin/audit-logs/actions')
      .then(({ data }) => setActions(data))
      .catch(() => setActions([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (actionFilter) params.action = actionFilter
      const { data } = await apiClient.get('/admin/audit-logs', { params })
      setLogs(data.items)
      setTotal(data.total)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được nhật ký.'))
    } finally {
      setLoading(false)
    }
  }, [page, actionFilter])

  useEffect(() => {
    load()
  }, [load])

  const changeAction = (value) => {
    setActionFilter(value)
    setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const labelOf = (code) => actions.find((a) => a.code === code)?.label || code

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="space-y-1">
          <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
            Nhật ký thao tác
          </h1>
          <p className="text-slate-600">
            Ghi lại các thao tác quản trị có hậu quả, phục vụ đối chiếu khi cần.
          </p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <Alert variant="info">
          Nhật ký chỉ ghi các thao tác <strong>quản trị</strong> (đổi cấu hình, quản lý
          đề thi, quản lý người dùng). Hành vi của thí sinh trong kỳ thi nằm ở mục{' '}
            <strong>Báo cáo → nhật ký vi phạm</strong>.
        </Alert>

        <Select
          label="Loại thao tác"
          value={actionFilter}
          onChange={changeAction}
          options={[
            { value: '', label: 'Tất cả thao tác' },
            ...actions.map((a) => ({ value: a.code, label: a.label })),
          ]}
          className="w-72"
        />

        <Card>
          {loading ? (
            <div className="flex items-center gap-3 text-slate-500 py-8 justify-center">
              <Icon name="refresh" size={20} />
              Đang tải…
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Icon name="history" size={32} className="text-slate-300 mx-auto" />
              <p className="mt-3">Chưa có thao tác nào được ghi nhận.</p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md">Thời gian</th>
                    <th className="px-6 py-3 font-label-md">Người thực hiện</th>
                    <th className="px-6 py-3 font-label-md">Thao tác</th>
                    <th className="px-6 py-3 font-label-md">Địa chỉ IP</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50">
                      <td className="px-6 py-3 text-slate-600 text-xs">
                        {formatDateTime(log.created_at)}
                      </td>
                      <td className="px-6 py-3">
                        <span className="font-mono text-xs text-slate-700">
                          {log.username || 'hệ thống'}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <Badge tone={ACTION_TONE[log.action] || 'neutral'}>
                          {labelOf(log.action)}
                        </Badge>
                      </td>
                      <td className="px-6 py-3 font-mono text-xs text-slate-500">
                        {log.ip_address || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Phân trang */}
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
            <p className="text-sm text-slate-500">
              Tổng {total} bản ghi · Trang {page}/{totalPages}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="btn-outline btn-sm"
              >
                <Icon name="chevron_left" size={16} />
                Trước
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="btn-outline btn-sm"
              >
                Sau
                <Icon name="chevron_right" size={16} />
              </button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
