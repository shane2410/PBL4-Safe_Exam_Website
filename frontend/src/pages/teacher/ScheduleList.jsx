import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Input from '../../components/common/Input'
import Select from '../../components/common/Select'
import Modal from '../../components/common/Modal'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import teacherService from '../../services/teacherService'
import { extractErrorMessage } from '../../services/apiClient'
import { SCHEDULE_STATUS, formatDateTime } from '../../utils/labels'

/** Chuyển datetime-local (giờ địa phương) sang ISO để gửi lên server. */
function toLocalInputValue(date) {
  const d = new Date(date)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function defaultWindow() {
  const start = new Date(Date.now() + 60 * 60 * 1000)
  const end = new Date(Date.now() + 3 * 60 * 60 * 1000)
  return { start_time: toLocalInputValue(start), end_time: toLocalInputValue(end) }
}

const EMPTY_FORM = { id: null, exam_id: '', room_code: '', status: 'SCHEDULED', ...defaultWindow() }

/** Lịch thi & Ca thi (Teacher). */
export default function ScheduleList() {
  const navigate = useNavigate()
  const [schedules, setSchedules] = useState([])
  const [exams, setExams] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [list, examList] = await Promise.all([
        teacherService.getSchedules(),
        teacherService.getExams(),
      ])
      setSchedules(list)
      setExams(examList)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được danh sách ca thi.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setForm({ ...EMPTY_FORM, exam_id: exams[0]?.id ?? '', room_code: randomRoomCode() })
    setFormError('')
    setEditing('new')
  }

  const openEdit = (s) => {
    setForm({
      id: s.id,
      exam_id: s.exam_id,
      room_code: s.room_code,
      status: s.status,
      start_time: toLocalInputValue(s.start_time),
      end_time: toLocalInputValue(s.end_time),
    })
    setFormError('')
    setEditing(s.id)
  }

  const save = async () => {
    setSaving(true)
    setFormError('')
    try {
      const payload = {
        exam_id: Number(form.exam_id),
        room_code: form.room_code.trim().toUpperCase(),
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
        status: form.status,
      }
      if (editing === 'new') {
        await teacherService.createSchedule(payload)
      } else {
        await teacherService.updateSchedule(editing, payload)
      }
      setEditing(null)
      load()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Không lưu được ca thi.'))
    } finally {
      setSaving(false)
    }
  }

  const examTitle = (id) => exams.find((e) => e.id === id)?.title || 'Đề thi đã xoá'

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
              Lịch thi & Ca thi
            </h1>
            <p className="text-slate-600">
              Tạo ca thi và sinh mã phòng để thí sinh truy cập.
            </p>
          </div>
          <button type="button" onClick={openCreate} className="btn-primary flex-shrink-0">
            <Icon name="add" size={18} />
            Tạo ca thi
          </button>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <Card>
          {loading ? (
            <div className="flex items-center gap-3 text-slate-500 py-8 justify-center">
              <Icon name="refresh" size={20} />
              Đang tải…
            </div>
          ) : schedules.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Icon name="event" size={32} className="text-slate-300 mx-auto" />
              <p className="mt-3">Chưa có ca thi nào.</p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md">Mã phòng</th>
                    <th className="px-6 py-3 font-label-md">Đề thi</th>
                    <th className="px-6 py-3 font-label-md">Bắt đầu</th>
                    <th className="px-6 py-3 font-label-md">Kết thúc</th>
                    <th className="px-6 py-3 font-label-md">Trạng thái</th>
                    <th className="px-6 py-3 font-label-md text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {schedules.map((s) => {
                    const st = SCHEDULE_STATUS[s.status] || SCHEDULE_STATUS.SCHEDULED
                    return (
                      <tr key={s.id} className="hover:bg-slate-50">
                        <td className="px-6 py-3">
                          <code className="px-2 py-1 rounded bg-primary-50 text-primary-700 text-xs font-medium">
                            {s.room_code}
                          </code>
                        </td>
                        <td className="px-6 py-3 text-slate-800">{examTitle(s.exam_id)}</td>
                        <td className="px-6 py-3 text-slate-600">{formatDateTime(s.start_time)}</td>
                        <td className="px-6 py-3 text-slate-600">{formatDateTime(s.end_time)}</td>
                        <td className="px-6 py-3">
                          <Badge tone={st.tone}>{st.label}</Badge>
                        </td>
                        <td className="px-6 py-3">
                          <div className="flex justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => navigate(`/monitor/${s.id}?room=${s.room_code}`)}
                              title="Giám sát phòng thi"
                              className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                            >
                              <Icon name="monitoring" size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={() => navigate(`/teacher/reports?schedule=${s.id}`)}
                              title="Xem báo cáo"
                              className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                            >
                              <Icon name="query_stats" size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={() => openEdit(s)}
                              title="Sửa ca thi"
                              className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                            >
                              <Icon name="edit" size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-sm text-slate-500 mt-4">Tổng: {schedules.length} ca thi</p>
        </Card>
      </div>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Tạo ca thi' : 'Sửa ca thi'}
        footer={
          <>
            <button type="button" onClick={() => setEditing(null)} className="btn-ghost">
              Huỷ
            </button>
            <button type="button" onClick={save} disabled={saving} className="btn-primary">
              {saving ? 'Đang lưu…' : 'Lưu'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          {formError && <Alert variant="error">{formError}</Alert>}

          <Select
            label="Đề thi"
            value={form.exam_id}
            onChange={(v) => setForm((f) => ({ ...f, exam_id: v }))}
            options={exams.map((e) => ({ value: e.id, label: e.title }))}
          />

          <Input
            label="Mã phòng thi"
            value={form.room_code}
            onChange={(v) => setForm((f) => ({ ...f, room_code: v }))}
            placeholder="PBL4-EXAM-01"
            helper="Thí sinh nhập mã này để vào phòng. Không phân biệt hoa thường."
            disabled={editing !== 'new'}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Bắt đầu"
              type="datetime-local"
              value={form.start_time}
              onChange={(v) => setForm((f) => ({ ...f, start_time: v }))}
            />
            <Input
              label="Kết thúc"
              type="datetime-local"
              value={form.end_time}
              onChange={(v) => setForm((f) => ({ ...f, end_time: v }))}
            />
          </div>

          <Select
            label="Trạng thái"
            value={form.status}
            onChange={(v) => setForm((f) => ({ ...f, status: v }))}
            options={Object.entries(SCHEDULE_STATUS).map(([value, s]) => ({
              value,
              label: s.label,
            }))}
          />
        </div>
      </Modal>
    </div>
  )
}

/** Sinh mã phòng ngẫu nhiên dạng PBL4-EXAM-XX. */
function randomRoomCode() {
  const n = Math.floor(Math.random() * 90) + 10
  return `PBL4-EXAM-${n}`
}
