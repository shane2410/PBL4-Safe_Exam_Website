import { useEffect, useState } from 'react'
import Modal from './Modal'
import Input from './Input'
import Alert from './Alert'
import Icon from './Icon'
import teacherService from '../../services/teacherService'
import { extractErrorMessage } from '../../services/apiClient'

/**
 * Quản lý môn học.
 *
 * Trước đây backend có `POST /questions/subjects` nhưng không có giao diện gọi tới,
 * nên giảng viên không thể tạo môn mới từ hệ thống — phải sửa tay trong database.
 * Component này bịt lỗ hổng đó.
 *
 * Không cho sửa/xoá ở đây: đề thi và câu hỏi đang tham chiếu tới môn, xoá sẽ
 * làm hỏng dữ liệu. Muốn đổi tên thì tạo môn mới rồi chuyển câu hỏi sang.
 */
export default function SubjectModal({ open, onClose, subjects = [], onChanged }) {
  const [form, setForm] = useState({ code: '', name: '' })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setForm({ code: '', name: '' })
      setError('')
      setSuccess('')
    }
  }, [open])

  const handleCreate = async () => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const created = await teacherService.createSubject({
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
      })
      setSuccess(`Đã tạo môn học ${created.code}.`)
      setForm({ code: '', name: '' })
      await onChanged?.()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tạo được môn học.'))
    } finally {
      setSaving(false)
    }
  }

  /** Tự sinh mã môn từ tên, ví dụ "Hệ điều hành" -> "HE-DIEU-HANH" (tối đa 20 ký tự). */
  const suggestCode = () => {
    const name = form.name.trim()
    if (!name) return
    const code = name
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/đ/gi, 'D')
      .replace(/[^a-zA-Z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .toUpperCase()
      .slice(0, 20)
    if (code) setForm((f) => ({ ...f, code }))
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Môn học"
      maxWidth="max-w-lg"
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-ghost">
            Đóng
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={saving || !form.code.trim() || !form.name.trim()}
            className="btn-primary"
          >
            {saving ? 'Đang tạo…' : 'Thêm môn học'}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <Alert variant="error">{error}</Alert>}
        {success && <Alert variant="success">{success}</Alert>}

        {/* Danh sách môn hiện có */}
        <div>
          <p className="text-body-md-medium text-slate-700 mb-2">
            Đang có {subjects.length} môn học
          </p>
          {subjects.length === 0 ? (
            <p className="text-body-sm text-slate-500 py-4 text-center border border-dashed border-slate-200 rounded-lg">
              Chưa có môn học nào. Tạo môn đầu tiên bên dưới.
            </p>
          ) : (
            <ul className="space-y-1.5 max-h-48 overflow-y-auto">
              {subjects.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg border border-slate-200"
                >
                  <div className="min-w-0">
                    <span className="font-mono text-body-sm text-primary font-medium">
                      {s.code}
                    </span>
                    <span className="ml-2 text-body-sm text-slate-700 truncate">
                      {s.name}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Form thêm môn */}
        <div className="pt-4 border-t border-slate-100 space-y-3">
          <p className="text-body-md font-semibold text-slate-800 flex items-center gap-2">
            <Icon name="add" size={16} />
            Thêm môn học mới
          </p>

          <Input
            label="Tên môn học"
            value={form.name}
            onChange={(v) => setForm((f) => ({ ...f, name: v }))}
            onBlur={suggestCode}
            placeholder="Ví dụ: Hệ điều hành"
          />

          <Input
            label="Mã môn học"
            value={form.code}
            onChange={(v) => setForm((f) => ({ ...f, code: v.toUpperCase() }))}
            placeholder="Ví dụ: HDH101"
            helper="Dùng để tra cứu và hiển thị. Bấm ra ngoài ô tên môn để hệ thống gợi ý mã."
          />

          <p className="text-xs text-slate-400">
            Môn đã có câu hỏi hoặc đề thi không thể xoá — nếu cần đổi, hãy tạo môn mới
            rồi chuyển sang.
          </p>
        </div>
      </div>
    </Modal>
  )
}
