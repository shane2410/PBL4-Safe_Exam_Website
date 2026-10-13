import { useCallback, useEffect, useState } from 'react'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Input from '../../components/common/Input'
import Select from '../../components/common/Select'
import Modal from '../../components/common/Modal'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import ImportQuestionsModal from './ImportQuestionsModal'
import SubjectModal from '../../components/common/SubjectModal'
import teacherService from '../../services/teacherService'
import { extractErrorMessage } from '../../services/apiClient'
import { QUESTION_TYPES, DIFFICULTIES } from '../../utils/labels'

const EMPTY_FORM = {
  id: null,
  content: '',
  subject_id: '',
  type: 'SINGLE_CHOICE',
  difficulty: 'MEDIUM',
  options: [
    { content: '', is_correct: true, order_index: 0 },
    { content: '', is_correct: false, order_index: 1 },
  ],
}

/**
 * Ngân hàng câu hỏi (Teacher).
 * Lọc theo môn / độ khó / từ khoá — tham số lọc được gửi lên server để escape
 * ký tự đặc biệt ở tầng DB (xem `question_service.escape_like`).
 */
export default function QuestionBank() {
  const [questions, setQuestions] = useState([])
  const [subjects, setSubjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [filters, setFilters] = useState({ search: '', subject_id: '', difficulty: '' })
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)
  const [importOpen, setImportOpen] = useState(false)
  const [subjectOpen, setSubjectOpen] = useState(false)
  const [downloadingTpl, setDownloadingTpl] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = {}
      if (filters.search.trim()) params.search = filters.search.trim()
      if (filters.subject_id) params.subject_id = filters.subject_id
      if (filters.difficulty) params.difficulty = filters.difficulty
      const [qs, subs] = await Promise.all([
        teacherService.getQuestions(params),
        teacherService.getSubjects(),
      ])
      setQuestions(qs)
      setSubjects(subs)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được danh sách câu hỏi.'))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setForm({ ...EMPTY_FORM, subject_id: subjects[0]?.id ?? '' })
    setFormError('')
    setEditing('new')
  }

  const openEdit = (q) => {
    setForm({
      id: q.id,
      content: q.content,
      subject_id: q.subject_id,
      type: q.type,
      difficulty: q.difficulty,
      options: (q.options || []).map((o, i) => ({
        content: o.content,
        is_correct: o.is_correct,
        order_index: i,
      })),
    })
    setFormError('')
    setEditing(q.id)
  }

  const setOption = (idx, patch) => {
    setForm((f) => ({
      ...f,
      options: f.options.map((o, i) => (i === idx ? { ...o, ...patch } : o)),
    }))
  }

  const addOption = () => {
    setForm((f) => ({
      ...f,
      options: [
        ...f.options,
        { content: '', is_correct: false, order_index: f.options.length },
      ],
    }))
  }

  const removeOption = (idx) => {
    setForm((f) => ({ ...f, options: f.options.filter((_, i) => i !== idx) }))
  }

  /**
   * Với câu chọn một / nhiều: bấm vào ô đúng để chuyển thành đáp án đúng.
   * Với câu nhập: các ô đáp án không dùng nên ẩn đi.
   */
  const toggleCorrect = (idx) => {
    setForm((f) => {
      if (f.type === 'FILL_BLANK') return f
      if (f.type === 'SINGLE_CHOICE') {
        return {
          ...f,
          options: f.options.map((o, i) => ({ ...o, is_correct: i === idx })),
        }
      }
      return {
        ...f,
        options: f.options.map((o, i) => (i === idx ? { ...o, is_correct: !o.is_correct } : o)),
      }
    })
  }

  const save = async () => {
    setSaving(true)
    setFormError('')
    try {
      const payload = {
        subject_id: Number(form.subject_id),
        content: form.content,
        type: form.type,
        difficulty: form.difficulty,
        options:
          form.type === 'FILL_BLANK'
            ? []
            : form.options
                .filter((o) => o.content.trim())
                .map((o, i) => ({
                  content: o.content,
                  is_correct: o.is_correct,
                  order_index: i,
                })),
      }
      if (editing === 'new') {
        await teacherService.createQuestion(payload)
      } else {
        await teacherService.updateQuestion(editing, payload)
      }
      setEditing(null)
      load()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Không lưu được câu hỏi.'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    try {
      await teacherService.deleteQuestion(deleting.id)
      setDeleting(null)
      load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không xoá được câu hỏi.'))
      setDeleting(null)
    }
  }

  const subjectName = (id) => subjects.find((s) => s.id === id)?.code || '—'

  /** Tải file .docx mẫu về máy để điền câu hỏi. */
  const downloadTemplate = async () => {
    setError('')
    setDownloadingTpl(true)
    try {
      await teacherService.downloadTemplate()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được file mẫu.'))
    } finally {
      setDownloadingTpl(false)
    }
  }

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
              Ngân hàng câu hỏi
            </h1>
            <p className="text-slate-600">
              Quản lý câu hỏi theo môn học và độ khó, dùng để tạo đề thi.
            </p>
          </div>
          {/* Gom nút thành một cụm: ưu tiên hành động chính bên phải */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={downloadTemplate}
              disabled={downloadingTpl}
              title="Tải file Word mẫu để điền câu hỏi"
              className="btn-ghost"
            >
              <Icon name="download" size={18} />
              {downloadingTpl ? 'Đang tải…' : 'File mẫu'}
            </button>
            <button
              type="button"
              onClick={() => setImportOpen(true)}
              className="btn-outline"
            >
              <Icon name="upload_file" size={18} />
              Nhập từ Word
            </button>
            <button type="button" onClick={openCreate} className="btn-primary">
              <Icon name="add" size={18} />
              Thêm câu hỏi
            </button>
          </div>
        </div>

        {error && <Alert variant="error">{error}</Alert>}

        {/* Bộ lọc */}
        <div className="flex flex-wrap gap-3 items-end">
          <Input
            label="Tìm kiếm"
            value={filters.search}
            onChange={(v) => setFilters((f) => ({ ...f, search: v }))}
            placeholder="Nội dung câu hỏi…"
            className="flex-1 min-w-[240px]"
          />
          <div className="relative">
            <Select
              label="Môn học"
              value={filters.subject_id}
              onChange={(v) => setFilters((f) => ({ ...f, subject_id: v }))}
              options={[
                { value: '', label: 'Mọi môn học' },
                ...subjects.map((s) => ({ value: s.id, label: s.code })),
              ]}
              className="w-44"
            />
            <button
              type="button"
              onClick={() => setSubjectOpen(true)}
              title="Thêm / xem danh sách môn học"
              className="absolute right-2 top-7 p-1 rounded text-slate-400 hover:text-primary hover:bg-primary-50 transition-colors"
            >
              <Icon name="add" size={16} />
            </button>
          </div>
          <Select
            label="Độ khó"
            value={filters.difficulty}
            onChange={(v) => setFilters((f) => ({ ...f, difficulty: v }))}
            options={[
              { value: '', label: 'Mọi độ khó' },
              { value: 'EASY', label: 'Dễ' },
              { value: 'MEDIUM', label: 'Trung bình' },
              { value: 'HARD', label: 'Khó' },
            ]}
            className="w-40"
          />
        </div>

        <Card>
          {loading ? (
            <div className="flex items-center gap-3 text-slate-500 py-8 justify-center">
              <Icon name="refresh" size={20} />
              Đang tải…
            </div>
          ) : questions.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Icon name="description" size={32} className="text-slate-300 mx-auto" />
              <p className="mt-3">Không có câu hỏi nào khớp bộ lọc.</p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md">Nội dung</th>
                    <th className="px-6 py-3 font-label-md">Môn</th>
                    <th className="px-6 py-3 font-label-md">Độ khó</th>
                    <th className="px-6 py-3 font-label-md">Loại</th>
                    <th className="px-6 py-3 font-label-md text-center">Đáp án</th>
                    <th className="px-6 py-3 font-label-md text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {questions.map((q) => {
                    const diff = DIFFICULTIES[q.difficulty] || DIFFICULTIES.MEDIUM
                    return (
                      <tr key={q.id} className="hover:bg-slate-50">
                        <td className="px-6 py-3 text-slate-800">
                          <p className="line-clamp-2 max-w-xl">{q.content}</p>
                        </td>
                        <td className="px-6 py-3">
                          <Badge tone="neutral">{subjectName(q.subject_id)}</Badge>
                        </td>
                        <td className="px-6 py-3">
                          <Badge tone={diff.tone}>{diff.label}</Badge>
                        </td>
                        <td className="px-6 py-3 text-slate-600">
                          {QUESTION_TYPES[q.type] || q.type}
                        </td>
                        <td className="px-6 py-3 text-center text-slate-600">
                          {(q.options || []).filter((o) => o.is_correct).length || '—'}
                        </td>
                        <td className="px-6 py-3">
                          <div className="flex justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => openEdit(q)}
                              title="Sửa"
                              className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                            >
                              <Icon name="edit" size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleting(q)}
                              title="Xoá"
                              className="p-2 rounded-md text-slate-500 hover:text-error hover:bg-error-50 transition-colors"
                            >
                              <Icon name="delete" size={16} />
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
          <p className="text-sm text-slate-500 mt-4">Tổng: {questions.length} câu hỏi</p>
        </Card>
      </div>

      {/* Form thêm / sửa */}
      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Thêm câu hỏi' : 'Sửa câu hỏi'}
        maxWidth="max-w-2xl"
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

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Môn học"
              value={form.subject_id}
              onChange={(v) => setForm((f) => ({ ...f, subject_id: v }))}
              options={subjects.map((s) => ({ value: s.id, label: `${s.code} — ${s.name}` }))}
            />
            <Select
              label="Loại câu hỏi"
              value={form.type}
              onChange={(v) => setForm((f) => ({ ...f, type: v }))}
              options={Object.entries(QUESTION_TYPES).map(([value, label]) => ({ value, label }))}
            />
          </div>

          <Select
            label="Độ khó"
            value={form.difficulty}
            onChange={(v) => setForm((f) => ({ ...f, difficulty: v }))}
            options={Object.entries(DIFFICULTIES).map(([value, d]) => ({
              value,
              label: d.label,
            }))}
          />

          <div>
            <label className="label" htmlFor="q-content">
              Nội dung câu hỏi <span className="text-error">*</span>
            </label>
            <textarea
              id="q-content"
              rows={3}
              value={form.content}
              onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
              placeholder="Nhập nội dung câu hỏi…"
              className="w-full p-3 rounded-lg border border-slate-300 text-body-md
                         focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
            />
          </div>

          {form.type !== 'FILL_BLANK' && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="label mb-0">Các lựa chọn</span>
                <button type="button" onClick={addOption} className="text-sm text-primary hover:underline">
                  + Thêm lựa chọn
                </button>
              </div>
              <p className="helper mt-0 mb-3">
                Bấm ô tròn để đánh dấu đáp án đúng.
                {form.type === 'SINGLE_CHOICE' && ' Chỉ được đánh dấu một đáp án đúng.'}
              </p>
              <div className="space-y-2">
                {form.options.map((opt, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => toggleCorrect(i)}
                      title="Đánh dấu đáp án đúng"
                      className={`w-5 h-5 rounded-full border flex-shrink-0 flex items-center justify-center transition-colors ${
                        opt.is_correct
                          ? 'bg-success border-success'
                          : 'border-slate-300 hover:border-success'
                      }`}
                    >
                      {opt.is_correct && <Icon name="check" size={12} className="text-white" />}
                    </button>
                    <input
                      value={opt.content}
                      onChange={(e) => setOption(i, { content: e.target.value })}
                      placeholder={`Lựa chọn ${i + 1}`}
                      className="input flex-1"
                    />
                    {form.options.length > 2 && (
                      <button
                        type="button"
                        onClick={() => removeOption(i)}
                        className="p-2 text-slate-400 hover:text-error transition-colors flex-shrink-0"
                        title="Bỏ lựa chọn này"
                      >
                        <Icon name="close" size={16} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* Quản lý môn học */}
      <SubjectModal
        open={subjectOpen}
        onClose={() => setSubjectOpen(false)}
        subjects={subjects}
        onChanged={load}
      />

      {/* Nhập câu hỏi từ file .docx */}
      <ImportQuestionsModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        subjects={subjects}
        onImported={(result) => {
          setSuccess(result.message)
          load()
        }}
      />

      {/* Xác nhận xoá */}
      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Xoá câu hỏi"
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
          Xoá câu hỏi <strong>“{deleting?.content?.slice(0, 80)}…”</strong>?
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Câu hỏi đang nằm trong đề thi sẽ không xoá được — hãy gỡ khỏi đề trước.
        </p>
      </Modal>
    </div>
  )
}
