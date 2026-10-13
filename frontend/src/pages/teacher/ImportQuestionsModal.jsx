import { useRef, useState } from 'react'
import Modal from '../../components/common/Modal'
import Select from '../../components/common/Select'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Icon from '../../components/common/Icon'
import teacherService from '../../services/teacherService'
import { extractErrorMessage } from '../../services/apiClient'
import { DIFFICULTIES, QUESTION_TYPES } from '../../utils/labels'

const PREVIEW_LIMIT = 50

/**
 * Nhập câu hỏi hàng loạt từ file .docx — luôn qua 2 bước:
 *   1. Đọc thử (không gì được ghi vào CSDL) → hiện kết quả + danh sách lỗi
 *   2. GV xác nhận mới ghi thật
 *
 * Vì sao không import thẳng: GV tải nhầm file 200 câu, bấm "Import", xong mới thấy
 * 150 câu sai định dạng — dữ liệu đã bẩn thì sửa cũng mệt. Xem trước giúp
 * tránh hẳn tình huống đó.
 */
export default function ImportQuestionsModal({ open, onClose, subjects = [], onImported }) {
  const [subjectId, setSubjectId] = useState('')
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [downloadingTemplate, setDownloadingTemplate] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  const reset = () => {
    setPreview(null)
    setError('')
    setLoading(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setError('')
    setPreview(null)

    if (!subjectId) {
      setError('Hãy chọn môn học trước khi tải file lên.')
      e.target.value = ''
      return
    }

    setLoading(true)
    try {
      const result = await teacherService.previewImport(file, subjectId)
      setPreview(result)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không đọc được file.'))
    } finally {
      setLoading(false)
    }
  }

  const handleCommit = async () => {
    if (!preview) return
    setCommitting(true)
    setError('')
    try {
      const result = await teacherService.commitImport(preview.preview_token, subjectId)
      onImported?.(result)
      handleClose()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không nhập được câu hỏi.'))
    } finally {
      setCommitting(false)
    }
  }

  const downloadTemplate = async () => {
    setError('')
    setDownloadingTemplate(true)
    try {
      await teacherService.downloadTemplate()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được file mẫu.'))
    } finally {
      setDownloadingTemplate(false)
    }
  }

  const shown = preview?.questions?.slice(0, PREVIEW_LIMIT) || []
  const hasMore = (preview?.questions?.length || 0) > PREVIEW_LIMIT

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Nhập câu hỏi từ file Word"
      maxWidth="max-w-3xl"
      footer={
        preview ? (
          <>
            <span className="mr-auto text-sm text-slate-500">
              Sẽ nhập <strong className="text-slate-700">{preview.new_count}</strong> câu
            </span>
            <button type="button" onClick={handleClose} className="btn-ghost">
              Huỷ
            </button>
            <button
              type="button"
              onClick={handleCommit}
              disabled={committing || preview.new_count === 0}
              className="btn-primary"
            >
              {committing ? 'Đang nhập…' : `Xác nhận nhập ${preview.new_count} câu`}
            </button>
          </>
        ) : (
          <button type="button" onClick={handleClose} className="btn-ghost">
            Đóng
          </button>
        )
      }
    >
      <div className="space-y-4">
        {error && <Alert variant="error">{error}</Alert>}

        {/* Bước chuẩn bị */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Select
            label="Môn học nhận câu hỏi"
            value={subjectId}
            onChange={(v) => {
              setSubjectId(v)
              setPreview(null)
            }}
            options={[
              { value: '', label: 'Chọn môn học…' },
              ...subjects.map((s) => ({ value: s.id, label: `${s.code} — ${s.name}` })),
            ]}
          />

          <div>
            <span className="label">File .docx</span>
            <label
              htmlFor="import-file"
              className={`flex items-center justify-center gap-2 h-11 px-4 rounded-lg border-2 border-dashed
                transition-colors cursor-pointer ${
                  subjectId
                    ? 'border-slate-300 hover:border-primary hover:bg-primary-50'
                    : 'border-slate-200 opacity-60 cursor-not-allowed'
                }`}
            >
              <Icon name="upload_file" size={18} className="text-slate-500" />
              <span className="text-body-md text-slate-600">
                {loading ? 'Đang đọc…' : 'Chọn file .docx'}
              </span>
            </label>
            <input
              ref={fileRef}
              id="import-file"
              type="file"
              accept=".docx"
              onChange={handleFile}
              disabled={!subjectId || loading}
              className="hidden"
            />
            <p className="helper">Tối đa 5 MB. Chưa ghi gì vào CSDL cho tới khi bạn xác nhận.</p>
          </div>
        </div>

        {/* Tải file mẫu — đặt ngay cạnh ô chọn file vì đây là thao tác GV cần làm đầu tiên */}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={downloadTemplate}
            disabled={downloadingTemplate}
            className="btn-outline btn-sm"
          >
            <Icon name="download" size={16} />
            {downloadingTemplate ? 'Đang tải…' : 'Tải file .docx mẫu'}
          </button>
          <span className="text-xs text-slate-500">
            Chưa biết cách trình bày? Tải mẫu về điền theo, hệ thống đọc được cả bảng Word
            lẫn văn bản phân tách.
          </span>
        </div>

        {/* Kết quả đọc thử */}
        {preview && (
          <div className="space-y-3 pt-3 border-t border-slate-100">
            <Alert
              variant={preview.error_count > 0 ? 'warning' : 'success'}
              title={`Đọc thành công — định dạng: ${preview.format_label}`}
            >
              {preview.message}
            </Alert>

            {/* Chỉ số */}
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-slate-200 p-3 text-center">
                <div className="text-xl font-bold text-slate-900">{preview.parsed_count}</div>
                <div className="text-xs text-slate-500 mt-0.5">Câu đọc được</div>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 text-center">
                <div className="text-xl font-bold text-success">{preview.new_count}</div>
                <div className="text-xs text-slate-500 mt-0.5">Sẽ nhập</div>
              </div>
              <div className="rounded-lg border border-slate-200 p-3 text-center">
                <div
                  className={`text-xl font-bold ${
                    preview.error_count > 0 ? 'text-error' : 'text-slate-400'
                  }`}
                >
                  {preview.error_count}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">Dòng lỗi</div>
              </div>
            </div>

            {/* Danh sách lỗi */}
            {preview.errors.length > 0 && (
              <div className="rounded-lg border border-error/30 bg-error-50 p-3">
                <p className="text-body-md-medium text-error-700 mb-2">
                  Các dòng sau sẽ bị bỏ qua (không ảnh hưởng phần còn lại):
                </p>
                <ul className="space-y-1 max-h-32 overflow-y-auto">
                  {preview.errors.map((e, i) => (
                    <li key={i} className="text-xs text-error-700">
                      <span className="font-medium">
                        {e.row ? `Dòng ${e.row}` : 'Tài liệu'}:
                      </span>{' '}
                      {e.reason}
                      {e.snippet && (
                        <span className="text-error/70"> — “{e.snippet}”</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {preview.duplicate_count > 0 && (
              <div className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-body-sm text-warning-900">
                {preview.duplicate_count} câu trùng với câu hỏi đã có trong ngân hàng
                (khớp nội dung không phân biệt hoa thường và dấu câu) nên sẽ được bỏ qua.
              </div>
            )}

            {/* Xem trước câu hỏi */}
            {shown.length > 0 && (
              <div>
                <p className="text-body-md-medium text-slate-700 mb-2">
                  Xem trước {shown.length}
                  {hasMore ? ` trong ${preview.questions.length}` : ''} câu đầu:
                </p>
                <ul className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {shown.map((q, i) => (
                    <li key={i} className="p-3 rounded-lg border border-slate-200">
                      <p className="text-body-sm text-slate-800 line-clamp-2">
                        {q.content}
                      </p>
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        <Badge tone="primary">{QUESTION_TYPES[q.type]}</Badge>
                        <Badge tone={(DIFFICULTIES[q.difficulty] || DIFFICULTIES.MEDIUM).tone}>
                          {(DIFFICULTIES[q.difficulty] || DIFFICULTIES.MEDIUM).label}
                        </Badge>
                        {q.options.map((o, oi) =>
                          o.is_correct ? (
                            <span
                              key={oi}
                              className="chip bg-success-50 text-success-700 border border-success/30"
                            >
                              Đúng: {o.content.slice(0, 24)}
                              {o.content.length > 24 ? '…' : ''}
                            </span>
                          ) : null,
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
