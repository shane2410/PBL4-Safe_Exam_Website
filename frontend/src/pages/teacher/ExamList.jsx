import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Input from '../../components/common/Input'
import Select from '../../components/common/Select'
import Modal from '../../components/common/Modal'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import teacherService from '../../services/teacherService'
import { extractErrorMessage } from '../../services/apiClient'
import { formatDateTime } from '../../utils/labels'

const EMPTY_FORM = {
  id: null,
  title: '',
  subject_id: '',
  duration_minutes: 60,
  total_score: 10,
  is_shuffled: true,
  require_safe_browser: false,
}

/** Danh sách đề thi (Teacher). */
export default function ExamList() {
  const navigate = useNavigate()
  const [exams, setExams] = useState([])
  const [subjects, setSubjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [list, subs] = await Promise.all([
        teacherService.getExams(),
        teacherService.getSubjects(),
      ])
      setExams(list)
      setSubjects(subs)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được danh sách đề thi.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setForm({ ...EMPTY_FORM, subject_id: subjects[0]?.id ?? '' })
    setFormError('')
    setEditing('new')
  }

  const openEdit = (e) => {
    setForm({
      id: e.id,
      title: e.title,
      subject_id: e.subject_id,
      duration_minutes: e.duration_minutes,
      total_score: e.total_score,
      is_shuffled: e.is_shuffled,
      require_safe_browser: e.require_safe_browser,
    })
    setFormError('')
    setEditing(e.id)
  }

  const save = async () => {
    setSaving(true)
    setFormError('')
    try {
      const payload = {
        title: form.title,
        subject_id: Number(form.subject_id),
        duration_minutes: Number(form.duration_minutes),
        total_score: Number(form.total_score),
        is_shuffled: form.is_shuffled,
        require_safe_browser: form.require_safe_browser,
      }
      if (editing === 'new') {
        const created = await teacherService.createExam(payload)
        setEditing(null)
        // Đề mới chưa có câu hỏi -> đưa thẳng tới trang cấu hình an toàn
        navigate(`/teacher/exams/${created.id}`)
        return
      }
      await teacherService.updateExam(editing, payload)
      setEditing(null)
      load()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Không lưu được đề thi.'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    try {
      await teacherService.deleteExam(deleting.id)
      setDeleting(null)
      load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không xoá được đề thi.'))
      setDeleting(null)
    }
  }

  const subjectLabel = (id) => subjects.find((s) => s.id === id)?.code || '—'

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
              Đề thi
            </h1>
            <p className="text-slate-600">
              Tạo đề thi và cấu hình cờ yêu cầu Safe Exam Browser cho từng đề.
            </p>
          </div>
          <button type="button" onClick={openCreate} className="btn-primary flex-shrink-0">
            <Icon name="add" size={18} />
            Tạo đề thi
          </button>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        <Card>
          {loading ? (
            <div className="flex items-center gap-3 text-slate-500 py-8 justify-center">
              <Icon name="refresh" size={20} />
              Đang tải…
            </div>
          ) : exams.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Icon name="school" size={32} className="text-slate-300 mx-auto" />
              <p className="mt-3">Chưa có đề thi nào.</p>
              <button type="button" onClick={openCreate} className="btn-primary mt-4">
                <Icon name="add" size={18} />
                Tạo đề thi đầu tiên
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md">Tiêu đề</th>
                    <th className="px-6 py-3 font-label-md">Môn</th>
                    <th className="px-6 py-3 font-label-md text-center">Câu hỏi</th>
                    <th className="px-6 py-3 font-label-md text-center">Thời lượng</th>
                    <th className="px-6 py-3 font-label-md">Yêu cầu SEB</th>
                    <th className="px-6 py-3 font-label-md">Ngày tạo</th>
                    <th className="px-6 py-3 font-label-md text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {exams.map((e) => (
                    <tr key={e.id} className="hover:bg-slate-50">
                      <td className="px-6 py-3">
                        <Link
                          to={`/teacher/exams/${e.id}`}
                          className="font-medium text-slate-800 hover:text-primary"
                        >
                          {e.title}
                        </Link>
                      </td>
                      <td className="px-6 py-3">
                        <Badge tone="neutral">{subjectLabel(e.subject_id)}</Badge>
                      </td>
                      <td className="px-6 py-3 text-center text-slate-600">
                        {e.question_count ?? 0}
                      </td>
                      <td className="px-6 py-3 text-center text-slate-600">
                        {e.duration_minutes} phút
                      </td>
                      <td className="px-6 py-3">
                        {e.require_safe_browser ? (
                          <Badge tone="primary" icon="security">
                            Bắt buộc
                          </Badge>
                        ) : (
                          <span className="text-slate-400">Không</span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-slate-500">{formatDateTime(e.created_at)}</td>
                      <td className="px-6 py-3">
                        <div className="flex justify-end gap-2">
                          <Link
                            to={`/teacher/exams/${e.id}`}
                            title="Cấu hình khoá an toàn"
                            className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                          >
                            <Icon name="settings" size={16} />
                          </Link>
                          <button
                            type="button"
                            onClick={() => openEdit(e)}
                            title="Sửa thông tin"
                            className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                          >
                            <Icon name="edit" size={16} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleting(e)}
                            title="Xoá"
                            className="p-2 rounded-md text-slate-500 hover:text-error hover:bg-error-50 transition-colors"
                          >
                            <Icon name="delete" size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-sm text-slate-500 mt-4">Tổng: {exams.length} đề thi</p>
        </Card>
      </div>

      {/* Form tạo / sửa đề thi */}
      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Tạo đề thi' : 'Sửa thông tin đề thi'}
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

          <Input
            label="Tiêu đề đề thi"
            value={form.title}
            onChange={(v) => setForm((f) => ({ ...f, title: v }))}
            placeholder="Ví dụ: Kiểm tra giữa kỳ môn Hệ điều hành"
          />

          <Select
            label="Môn học"
            value={form.subject_id}
            onChange={(v) => setForm((f) => ({ ...f, subject_id: v }))}
            options={subjects.map((s) => ({ value: s.id, label: `${s.code} — ${s.name}` }))}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Thời lượng (phút)"
              type="number"
              value={form.duration_minutes}
              onChange={(v) => setForm((f) => ({ ...f, duration_minutes: v }))}
            />
            <Input
              label="Tổng điểm"
              type="number"
              value={form.total_score}
              onChange={(v) => setForm((f) => ({ ...f, total_score: v }))}
            />
          </div>

          <Alert variant="info">
            Câu hỏi được thêm ở trang cấu hình đề. Cờ “yêu cầu Safe Exam Browser” ở
            đây là cờ <strong>cấp đề</strong> — chỉ có hiệu lực khi cờ cấp hệ thống
            đang bật.
          </Alert>
        </div>
      </Modal>

      {/* Xác nhận xoá */}
      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Xoá đề thi"
        footer={
          <>
            <button type="button" onClick={() => setDeleting(null)} className="btn-ghost">
              Huỷ
            </button>
            <button type="button" onClick={remove} className="btn-danger">
              Xoá
            </button>
          </>
        }
      >
        <p className="text-slate-700">
          Xoá đề thi <strong>“{deleting?.title}”</strong>?
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Đề đang gắn vào ca thi sẽ không xoá được — hãy huỷ các ca thi liên quan trước.
        </p>
      </Modal>
    </div>
  )
}
