import { useEffect, useState } from 'react'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import apiClient, { extractErrorMessage } from '../../services/apiClient'

/** Danh sách kết quả thi của thí sinh đang đăng nhập. */
export default function ExamResults() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    apiClient
      .get('/exam-sessions/my-results')
      .then(({ data }) => {
        if (!cancelled) setResults(data || [])
      })
      .catch((err) => {
        if (!cancelled) setError(extractErrorMessage(err, 'Không tải được kết quả.'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-3 text-slate-500">
        <Icon name="refresh" size={20} />
        Đang tải kết quả…
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="space-y-1">
          <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
            Kết quả của tôi
          </h1>
          <p className="text-slate-600">Lịch sử các bài thi bạn đã hoàn thành.</p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        {results.length === 0 ? (
          <Card>
            <p className="text-slate-500 text-center py-8">Chưa có kết quả nào.</p>
          </Card>
        ) : (
          <Card>
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md">Đề thi</th>
                    <th className="px-6 py-3 font-label-md">Điểm</th>
                    <th className="px-6 py-3 font-label-md">Cách nộp</th>
                    <th className="px-6 py-3 font-label-md">Điểm rủi ro</th>
                    <th className="px-6 py-3 font-label-md">Thời gian nộp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {results.map((r) => (
                    <tr key={r.session_id} className="hover:bg-slate-50">
                      <td className="px-6 py-3 font-medium text-slate-800">
                        {r.exam_title}
                      </td>
                      <td className="px-6 py-3">
                        <span className="font-semibold text-slate-800">
                          {r.final_score ?? 0}
                        </span>
                        <span className="text-slate-400"> / {r.total_score}</span>
                      </td>
                      <td className="px-6 py-3 text-slate-600">{r.submit_type}</td>
                      <td className="px-6 py-3">
                        <Badge
                          tone={
                            r.risk_score >= 100
                              ? 'error'
                              : r.risk_score >= 50
                                ? 'warning'
                                : 'success'
                          }
                        >
                          {r.risk_score}
                        </Badge>
                      </td>
                      <td className="px-6 py-3 text-slate-500">
                        {r.submitted_at
                          ? new Date(r.submitted_at).toLocaleString('vi-VN')
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
