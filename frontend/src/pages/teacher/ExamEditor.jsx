import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Card from '../../components/common/Card'
import Toggle from '../../components/common/Toggle'
import Input from '../../components/common/Input'
import Select from '../../components/common/Select'
import Modal from '../../components/common/Modal'
import Alert from '../../components/common/Alert'
import Badge from '../../components/common/Badge'
import Icon from '../../components/common/Icon'
import apiClient, { extractErrorMessage } from '../../services/apiClient'
import teacherService from '../../services/teacherService'
import policyService, {
  DEFAULT_SECURITY_CONFIG,
  SECURITY_MECHANISM_LABELS,
  TOGGLE_MECHANISMS,
} from '../../services/policyService'
import SubjectModal from '../../components/common/SubjectModal'
import { DIFFICULTIES, QUESTION_TYPES } from '../../utils/labels'

/**
 * Trang chỉnh sửa đề thi (Teacher).
 *
 * Chứa CỜ CẤP ĐỀ `require_safe_browser` — nhánh thứ hai của quyết định
 * "only through safe exam browser". Hiệu lực = cờ đề AND cờ hệ thống.
 * GV có thể TẮT cờ đề ngay cả khi cả hệ thống đang bật, để một đề bất thường
 * không chặn nhầm cả lớp.
 */
export default function ExamEditor() {
  const { examId } = useParams()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [exam, setExam] = useState(null)
  const [policy, setPolicy] = useState(DEFAULT_SECURITY_CONFIG)
  const [globalToggle, setGlobalToggle] = useState(false)
  const [subjects, setSubjects] = useState([])

  // --- Quản lý câu hỏi trong đề ---
  const [selectedQuestions, setSelectedQuestions] = useState([])
  const [bankQuestions, setBankQuestions] = useState([])
  const [pickerOpen, setPickerOpen] = useState(false)
  const [bankFilter, setBankFilter] = useState({ subject_id: '', difficulty: '', search: '' })
  const [subjectOpen, setSubjectOpen] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        // Lưu ý về shape dữ liệu:
        //   - apiClient.get(...) trả về axios response -> phải dùng `.data`
        //   - policyService.* đã bóc sẵn `data` bên trong -> dùng trực tiếp
        // Trước đây code dùng `policyRes.data` và `settingsRes.data` cho cả hai
        // loại, nên policy luôn rơi về mặc định và `settingsRes.data` là
        // undefined -> TypeError -> giáo viên không mở được đề nào.
        const [examRes, policy, subjectsRes] = await Promise.all([
          apiClient.get(`/exams/${examId}`),
          policyService.getExamPolicy(examId),
          apiClient.get('/questions/subjects'),
        ])
        if (cancelled) return

        setExam(examRes.data)
        setPolicy(policyService.normalize(policy))
        // Cờ hệ thống đi kèm trong detail đề (chỉ đọc), nên TEACHER không cần
        // gọi /admin/settings — endpoint đó chỉ dành cho ADMIN và sẽ trả 403.
        setGlobalToggle(Boolean(examRes.data.require_safe_browser_global))
        setSubjects(subjectsRes.data)

        // Nạp danh sách câu đã gán vào đề (ExamDetailResponse.exam_questions)
        const assigned = (examRes.data.exam_questions || []).map((eq) => ({
          question_id: eq.question_id,
          score: Number(eq.score),
          order_index: eq.order_index,
          content: eq.question?.content || '',
          type: eq.question?.type || '',
          difficulty: eq.question?.difficulty || '',
          question: eq.question,
        }))
        setSelectedQuestions(assigned.sort((a, b) => a.order_index - b.order_index))
      } catch (err) {
        if (!cancelled) setError(extractErrorMessage(err, 'Không tải được đề thi.'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [examId])

  /** Nạp ngân hàng câu hỏi mỗi khi mở hộp chọn, lọc theo bộ lọc hiện tại. */
  useEffect(() => {
    if (!pickerOpen) return
    const params = {}
    if (bankFilter.subject_id) params.subject_id = bankFilter.subject_id
    if (bankFilter.difficulty) params.difficulty = bankFilter.difficulty
    if (bankFilter.search.trim()) params.search = bankFilter.search.trim()

    teacherService
      .getQuestions(params)
      .then(setBankQuestions)
      .catch(() => setBankQuestions([]))
  }, [pickerOpen, bankFilter])

  const assignedIds = useMemo(
    () => new Set(selectedQuestions.map((q) => q.question_id)),
    [selectedQuestions],
  )

  const addQuestion = (question) => {
    setSelectedQuestions((prev) => [
      ...prev,
      {
        question_id: question.id,
        score: 1,
        order_index: prev.length,
        content: question.content,
        type: question.type,
        difficulty: question.difficulty,
        question,
      },
    ])
  }

  const removeQuestion = (questionId) => {
    setSelectedQuestions((prev) =>
      prev
        .filter((q) => q.question_id !== questionId)
        .map((q, i) => ({ ...q, order_index: i })),
    )
  }

  const setScore = (questionId, score) => {
    setSelectedQuestions((prev) =>
      prev.map((q) => (q.question_id === questionId ? { ...q, score } : q)),
    )
  }

  const moveQuestion = (index, direction) => {
    setSelectedQuestions((prev) => {
      const next = [...prev]
      const target = index + direction
      if (target < 0 || target >= next.length) return prev
      ;[next[index], next[target]] = [next[target], next[index]]
      return next.map((q, i) => ({ ...q, order_index: i }))
    })
  }

  const save = async () => {
    setSaving(true)
    setError('')
    setSuccess('')

    // Chặn lưu khi ĐÃ CÓ câu hỏi mà tổng điểm câu hỏi lệch tổng điểm đề — GV hay quên chỉnh,
    // gây ra chấm điểm sai khi thi. Nếu chưa có câu hỏi (đang tạo khung / chỉnh setting), cho phép lưu.
    const total = selectedQuestions.reduce((sum, q) => sum + (q.score || 0), 0)
    if (selectedQuestions.length > 0 && Math.abs(total - Number(exam.total_score || 0)) > 0.001) {
      setError(
        `Tổng điểm các câu hỏi (${total.toFixed(2)}) chưa khớp tổng điểm đề (${exam.total_score}). Hãy chỉnh lại trước khi lưu.`,
      )
      setSaving(false)
      return
    }

    try {
      await Promise.all([
        apiClient.put(`/exams/${examId}`, {
          title: exam.title,
          duration_minutes: exam.duration_minutes,
          total_score: exam.total_score,
          is_shuffled: exam.is_shuffled,
          require_safe_browser: exam.require_safe_browser,
          questions: selectedQuestions.map((q) => ({
            question_id: q.question_id,
            score: Number(q.score) || 0,
            order_index: q.order_index,
          })),
        }),
        policyService.setExamPolicy(examId, policy),
      ])
      setSuccess('Đã lưu thay đổi.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Không lưu được thay đổi.'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-3 text-slate-500">
        <Icon name="refresh" size={20} />
        Đang tải đề thi…
      </div>
    )
  }

  if (!exam) {
    return (
      <div className="p-8">
        <Alert variant="error">{error || 'Không tìm thấy đề thi.'}</Alert>
      </div>
    )
  }

  // Cờ đề chỉ có tác dụng khi cờ hệ thống đang bật — nói rõ để GV không bị nhầm
  const effectiveNow = exam.require_safe_browser && globalToggle

  // Tổng điểm các câu đã chọn — phải khớp `total_score` của đề
  const selectedTotal = selectedQuestions.reduce((sum, q) => sum + (q.score || 0), 0)
  const scoreMismatch = Math.abs(selectedTotal - Number(exam.total_score || 0)) > 0.001

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto space-y-6 pb-24">
        <div className="space-y-1">
          <nav className="text-xs text-slate-500 mb-1">
            <button
              type="button"
              onClick={() => navigate('/teacher/exams')}
              className="hover:text-primary"
            >
              Đề thi
            </button>
            {' / '}
            Chỉnh sửa
          </nav>
          <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
            {exam.title}
          </h1>
          <p className="text-slate-600">
            Thiết lập thông tin đề và chính sách khoá an toàn áp dụng cho phòng thi.
          </p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}
        {success && <Alert variant="success">{success}</Alert>}

        {/* Thông tin đề */}
        <Card icon="school" title="Thông tin đề thi">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Input
              label="Tiêu đề đề thi"
              value={exam.title}
              onChange={(v) => setExam((e) => ({ ...e, title: v }))}
            />
            <Select
              label="Môn học"
              value={exam.subject_id}
              onChange={(v) => setExam((e) => ({ ...e, subject_id: Number(v) }))}
              options={subjects.map((s) => ({ value: s.id, label: `${s.code} — ${s.name}` }))}
            />
            <Input
              label="Thời lượng (phút)"
              type="number"
              value={exam.duration_minutes}
              onChange={(v) => setExam((e) => ({ ...e, duration_minutes: Number(v) || 0 }))}
            />
            <Input
              label="Tổng điểm"
              type="number"
              value={exam.total_score}
              onChange={(v) => setExam((e) => ({ ...e, total_score: Number(v) || 0 }))}
            />
            <div className="flex items-end pb-1">
              <Toggle
                checked={exam.is_shuffled}
                onChange={(v) => setExam((e) => ({ ...e, is_shuffled: v }))}
                label="Trộn câu hỏi và đáp án"
                description="Thứ tự câu hỏi và lựa chọn được trộn riêng cho từng phiên thi."
              />
            </div>
          </div>
        </Card>

        {/* QUẢN LÝ CÂU HỎI TRONG ĐỀ */}
        <Card
          icon="description"
          title={`Câu hỏi trong đề (${selectedQuestions.length})`}
          action={
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              className="btn-outline btn-sm"
            >
              <Icon name="add" size={16} />
              Chọn từ ngân hàng
            </button>
          }
        >
          {selectedQuestions.length === 0 ? (
            <div className="text-center py-10 text-slate-500">
              <Icon name="description" size={30} className="text-slate-300 mx-auto" />
              <p className="mt-3">Đề thi chưa có câu hỏi nào.</p>
              <button
                type="button"
                onClick={() => setPickerOpen(true)}
                className="btn-primary mt-4"
              >
                <Icon name="add" size={18} />
                Chọn câu hỏi
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md text-center">#</th>
                    <th className="px-6 py-3 font-label-md">Nội dung</th>
                    <th className="px-6 py-3 font-label-md">Loại</th>
                    <th className="px-6 py-3 font-label-md text-center">Độ khó</th>
                    <th className="px-6 py-3 font-label-md text-center" style={{ width: 110 }}>
                      Điểm
                    </th>
                    <th className="px-6 py-3 font-label-md text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {selectedQuestions.map((q, i) => {
                    const diff = DIFFICULTIES[q.difficulty] || DIFFICULTIES.MEDIUM
                    return (
                      <tr key={q.question_id} className="hover:bg-slate-50">
                        <td className="px-6 py-3 text-center text-slate-400">{i + 1}</td>
                        <td className="px-6 py-3 text-slate-800">
                          <p className="line-clamp-2 max-w-lg">{q.content}</p>
                        </td>
                        <td className="px-6 py-3 text-slate-600">
                          {QUESTION_TYPES[q.type] || q.type}
                        </td>
                        <td className="px-6 py-3 text-center">
                          <Badge tone={diff.tone}>{diff.label}</Badge>
                        </td>
                        <td className="px-6 py-3">
                          <input
                            type="number"
                            step="0.25"
                            min="0"
                            value={q.score}
                            onChange={(e) =>
                              setScore(q.question_id, Number(e.target.value))
                            }
                            className="w-20 px-2 py-1.5 text-center rounded-md border border-slate-300
                                       focus:border-primary focus:ring-1 focus:ring-primary focus:outline-none"
                          />
                        </td>
                        <td className="px-6 py-3">
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => moveQuestion(i, -1)}
                              disabled={i === 0}
                              title="Lên"
                              className="p-1.5 rounded text-slate-500 hover:text-primary hover:bg-primary-50 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                            >
                              <Icon name="keyboard_arrow_up" size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={() => moveQuestion(i, 1)}
                              disabled={i === selectedQuestions.length - 1}
                              title="Xuống"
                              className="p-1.5 rounded text-slate-500 hover:text-primary hover:bg-primary-50 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                            >
                              <Icon name="keyboard_arrow_down" size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={() => removeQuestion(q.question_id)}
                              title="Gỡ khỏi đề"
                              className="p-1.5 rounded text-slate-500 hover:text-error hover:bg-error-50 transition-colors"
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

          <div
            className={`flex items-center justify-between mt-4 pt-4 border-t ${
              scoreMismatch ? 'border-warning-200' : 'border-slate-100'
            }`}
          >
            <p
              className={`text-sm font-medium ${
                scoreMismatch ? 'text-warning-700' : 'text-slate-600'
              }`}
            >
              Tổng điểm câu hỏi:{' '}
              <span className="font-semibold">{selectedTotal.toFixed(2)}</span> /{' '}
              {exam.total_score}
              {scoreMismatch && ' — chưa khớp, cần chỉnh trước khi lưu'}
            </p>
            {!scoreMismatch && selectedQuestions.length > 0 && (
              <span className="text-xs text-success flex items-center gap-1">
                <Icon name="check_circle" size={14} />
                Đã khớp
              </span>
            )}
          </div>
        </Card>

        {/* CỜ CẤP ĐỀ */}
        <Card accent icon="security" title="Yêu cầu Safe Exam Browser">
          <Toggle
            checked={exam.require_safe_browser}
            onChange={(v) => setExam((e) => ({ ...e, require_safe_browser: v }))}
            label="Đề thi này yêu cầu Safe Exam Browser Client"
            description="Đề này sẽ chỉ nhận SEB Client đã xác thực — nhưng chỉ khi cờ hệ thống cũng đang bật."
          />

          {!globalToggle && exam.require_safe_browser && (
            <Alert variant="warning" className="mt-4">
              Cờ hệ thống hiện đang <strong>TẮT</strong>, nên thiết lập này{' '}
              <strong>chưa có hiệu lực</strong>. Bật cờ ở trang Cấu hình hệ thống để
              áp dụng cho toàn hệ thống.
            </Alert>
          )}

          {effectiveNow && (
            <Alert variant="warning" className="mt-4">
              <strong>Đang có hiệu lực.</strong> Thí sinh truy cập bằng trình duyệt web
              sẽ vào phòng ở chế độ hạn chế và bị ghi log phục tra.
            </Alert>
          )}
        </Card>

        {/* Cấu hình khoá an toàn của đề */}
        <Card icon="lock" title="Cấu hình khoá an toàn của đề">
          <div className="space-y-4 divide-y divide-slate-100">
            {TOGGLE_MECHANISMS.map((key) => (
              <div key={key} className="py-3 first:pt-0 last:pb-0">
                <Toggle
                  checked={Boolean(policy[key])}
                  onChange={(v) => setPolicy((p) => ({ ...p, [key]: v }))}
                  label={SECURITY_MECHANISM_LABELS[key].label}
                  description={SECURITY_MECHANISM_LABELS[key].description}
                />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6 pt-5 border-t border-slate-100">
            <Input
              label="Ngưỡng chuyển tab tối đa"
              type="number"
              value={policy.max_tab_switch}
              onChange={(v) => setPolicy((p) => ({ ...p, max_tab_switch: Number(v) || 0 }))}
            />
            <Input
              label="Ngưỡng thoát toàn màn hình"
              type="number"
              value={policy.max_fullscreen_exit}
              onChange={(v) => setPolicy((p) => ({ ...p, max_fullscreen_exit: Number(v) || 0 }))}
            />
            <Input
              label="Đếm ngược yêu cầu quay lại (giây)"
              type="number"
              value={policy.warn_countdown_seconds}
              onChange={(v) =>
                setPolicy((p) => ({ ...p, warn_countdown_seconds: Number(v) || 0 }))
              }
            />
          </div>

          <div className="mt-5">
            <Toggle
              checked={policy.auto_submit_on_threshold}
              onChange={(v) => setPolicy((p) => ({ ...p, auto_submit_on_threshold: v }))}
              label="Tự động nộp bài khi vượt ngưỡng"
              description="Server sẽ tự nộp bài và lưu đầy đủ log làm căn cứ phúc tra."
            />
          </div>
        </Card>
      </div>

      {/* Thanh hành động dính đáy */}
      <div className="fixed bottom-0 right-0 left-[260px] bg-white border-t border-slate-200 px-8 py-3 flex items-center justify-between gap-4 shadow-sm z-20">
        <div className="flex-1 min-w-0">
          {error && (
            <p className="text-sm font-medium text-error truncate flex items-center gap-1.5" title={error}>
              <Icon name="warning" size={16} />
              {error}
            </p>
          )}
          {success && (
            <p className="text-sm font-medium text-success truncate flex items-center gap-1.5">
              <Icon name="check" size={16} />
              {success}
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button type="button" onClick={() => navigate('/teacher/exams')} className="btn-ghost">
            Huỷ
          </button>
          <button type="button" onClick={save} disabled={saving} className="btn-primary">
            {saving ? 'Đang lưu…' : 'Lưu thay đổi'}
          </button>
        </div>
      </div>
      <SubjectModal
        open={subjectOpen}
        onClose={() => setSubjectOpen(false)}
        subjects={subjects}
        onChanged={async () => {
          const list = await teacherService.getSubjects()
          setSubjects(list)
        }}
      />

      {/* Chọn câu hỏi từ ngân hàng */}
      <Modal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        title="Chọn câu hỏi từ ngân hàng"
        maxWidth="max-w-3xl"
        footer={
          <>
            <span className="mr-auto text-sm text-slate-500">
              Đã chọn {selectedQuestions.length} câu
            </span>
            <button type="button" onClick={() => setPickerOpen(false)} className="btn-primary">
              Xong
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex gap-3">
            <Input
              label="Tìm kiếm"
              value={bankFilter.search}
              onChange={(v) => setBankFilter((f) => ({ ...f, search: v }))}
              placeholder="Nội dung câu hỏi…"
              className="flex-1"
            />
            <Select
              label="Môn học"
              value={bankFilter.subject_id}
              onChange={(v) => setBankFilter((f) => ({ ...f, subject_id: v }))}
              options={[
                { value: '', label: 'Mọi môn' },
                ...subjects.map((s) => ({ value: s.id, label: s.code })),
              ]}
              className="w-36"
            />
            <Select
              label="Độ khó"
              value={bankFilter.difficulty}
              onChange={(v) => setBankFilter((f) => ({ ...f, difficulty: v }))}
              options={[
                { value: '', label: 'Mọi độ khó' },
                { value: 'EASY', label: 'Dễ' },
                { value: 'MEDIUM', label: 'Trung bình' },
                { value: 'HARD', label: 'Khó' },
              ]}
              className="w-36"
            />
          </div>

          {bankQuestions.length === 0 ? (
            <p className="text-center text-slate-500 py-10">
              Không có câu hỏi nào khớp bộ lọc.
            </p>
          ) : (
            <ul className="space-y-2 max-h-[45vh] overflow-y-auto">
              {bankQuestions.map((q) => {
                const already = assignedIds.has(q.id)
                const diff = DIFFICULTIES[q.difficulty] || DIFFICULTIES.MEDIUM
                return (
                  <li
                    key={q.id}
                    className={`flex items-start gap-3 p-3 rounded-lg border ${
                      already ? 'border-primary-100 bg-primary-50' : 'border-slate-200'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={already}
                      disabled={already}
                      onChange={() => addQuestion(q)}
                      className="mt-1 w-4 h-4 accent-primary flex-shrink-0"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-slate-800 line-clamp-2">{q.content}</p>
                      <div className="flex items-center gap-2 mt-1.5">
                        <Badge tone={diff.tone}>{diff.label}</Badge>
                        <span className="text-xs text-slate-400">
                          {QUESTION_TYPES[q.type] || q.type}
                        </span>
                        {already && (
                          <span className="text-xs text-primary font-medium">Đã có trong đề</span>
                        )}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </Modal>
    </div>
  )
}
