import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../../components/common/Icon'
import Badge from '../../components/common/Badge'
import Alert from '../../components/common/Alert'
import Modal from '../../components/common/Modal'
import PolicyGate from './PolicyGate'
import apiClient, { extractErrorMessage } from '../../services/apiClient'
import { SECURITY_MECHANISM_LABELS } from '../../services/policyService'

import useSecurityPolicy from './hooks/useSecurityPolicy'
import useFullscreenLock from './hooks/useFullscreenLock'
import useVisibilityMonitor from './hooks/useVisibilityMonitor'
import useKeyboardBlock from './hooks/useKeyboardBlock'
import useDevToolsDetector from './hooks/useDevToolsDetector'
import useNavigationLock from './hooks/useNavigationLock'
import useAutoSave from './hooks/useAutoSave'
import useViolationWarning from './hooks/useViolationWarning'

/** Đếm ngược định dạng mm:ss từ số giây còn lại. */
function formatCountdown(totalSeconds) {
  const safe = Math.max(0, totalSeconds)
  const m = Math.floor(safe / 60)
  const s = safe % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export default function ExamRoom() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const roomCode = searchParams.get('room') || ''

  const [state, setState] = useState(null)
  const [joining, setJoining] = useState(true)
  const [joinError, setJoinError] = useState('')
  const [sebBlocked, setSebBlocked] = useState(false)

  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [remaining, setRemaining] = useState(0)
  const [confirmSubmit, setConfirmSubmit] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  // Phiên đã bị khoá: server đã thu bài (cưỡng chế vì vượt ngưỡng, hoặc thí sinh
  // nộp xong). Mọi cơ chế giám sát phải DỪNG, và bộ đếm phải ngừng tăng.
  const [locked, setLocked] = useState(false)
  const [serverNotice, setServerNotice] = useState('')
  // Lỗi nộp bài CÓ THỂ THỬ LẠI (mạng, 5xx, timeout). Khi có giá trị, UI hiện
  // nút "Thử nộp lại". Trước đây `setLocked(true)` chạy trước request và
  // không bao giờ được gỡ, nên chỉ cần một lần mất mạng là thí sinh kẹt vĩnh
  // viễn ở màn hình khoá trong khi phiên phía server vẫn IN_PROGRESS và
  // KHÔNG được chấm điểm.
  const [submitError, setSubmitError] = useState('')
  // Loại nộp của lần gần nhất, để nút "Thử nộp lại" dùng lại đúng submit_type
  // (VD vẫn là AUTO_TIMEOUT, không âm thầm đổi thành MANUAL).
  const lastSubmitTypeRef = useRef('MANUAL')
  // false = đang ở màn "sẵn sàng", true = đã bấm Bắt đầu thi.
  // Bắt buộc có bước này vì trình duyệt chỉ cho gọi requestFullscreen() khi
  // người dùng vừa bấm chuột/phím.
  const [started, setStarted] = useState(false)
  const [startError, setStartError] = useState('')
  const [fullscreenBlocked, setFullscreenBlocked] = useState(false)

  // Chống gọi nộp bài hai lần (bấm tay + hết giờ + server force_submit).
  // Dùng ref vì `setSubmitting` là bất đồng bộ: hai sự kiện trong cùng một tick
  // vẫn có thể cùng đọc `submitting === false`.
  const submittingRef = useRef(false)
  // Đã nộp thành công: chặn mọi lần nộp lặp lại trong lúc chờ điều hướng.
  const submittedRef = useRef(false)
  // Chỉ tự nộp MỘT lần khi đồng hồ về 0.
  const autoSubmitFiredRef = useRef(false)
  // Luôn trỏ tới `flush` mới nhất của useAutoSave. `handleForceSubmit` được
  // useCallback với deps cố định nên nếu gọi trực tiếp `flush` nó sẽ giữ
  // closure cũ (đáp án cũ) — ref thì luôn đọc bản mới nhất.
  const flushAnswersRef = useRef(null)
  // Luôn trỏ tới `submitExam` mới nhất cho useEffect đếm ngược (tránh phải
  // thêm submitExam vào deps và tạo lại interval mỗi render).
  const submitExamRef = useRef(null)

  const join = useCallback(async () => {
    setJoining(true)
    setJoinError('')
    setSebBlocked(false)
    try {
      const { data } = await apiClient.post('/exam-sessions/join', {
        room_code: roomCode,
        client_type: 'web',
      })
      setState(data)
      setAnswers(data.saved_answers || {})
      setRemaining(data.remaining_seconds)
      setGateDismissed(false)
      // Vào lại phòng (sau lỗi/retry) là một lượt mới: cho phép tự nộp lại
      // khi đồng hồ về 0, và bỏ khoá chống nộp trùng của lượt trước.
      autoSubmitFiredRef.current = false
      submittingRef.current = false
      submittedRef.current = false
    } catch (err) {
      if (err?.response?.status === 403 && err.response.data?.detail === 'SEB_REQUIRED') {
        setSebBlocked(true)
      } else {
        setJoinError(extractErrorMessage(err, 'Không vào được phòng thi.'))
      }
    } finally {
      setJoining(false)
    }
  }, [roomCode])

  useEffect(() => {
    if (!roomCode) {
      setJoinError('Thiếu mã phòng thi. Vui lòng nhập mã trước khi vào phòng.')
      setJoining(false)
      return
    }
    join()
  }, [roomCode, join])

  // Định nghĩa TRƯỚC handleForceSubmit.
  // handleForceSubmit gọi submitExam; nếu khai báo sau bằng `const`, thì
  // khi server đẩy force_submit tới rất sớm (socket vừa kết nối lại lúc
  // mount) sẽ rơi vào vùng chết tạm (TDZ) và ném ReferenceError.
  const submitExam = async (submitType = 'MANUAL') => {
    if (!state?.session_token) return
    if (submittingRef.current || submittedRef.current) return
    submittingRef.current = true
    lastSubmitTypeRef.current = submitType
    setSubmitting(true)
    setSubmitError('')
    // Khoá ngay khi bắt đầu nộp (tránh bộ đếm vi phạm chạy tiếp trong lúc
    // request đang bay). Nếu nộp THẤT BẠI vì lỗi tạm thời, catch bên dưới
    // sẽ mở khoá lại — xem A8.
    setLocked(true)
    try {
      // ĐẨY NỐT ĐÁP ÁN ĐANG CHỜ TRƯỚC KHI NỘP.
      //
      // useAutoSave debounce 1.5s: nếu thí sinh chọn câu cuối rồi bấm "Nộp bài"
      // ngay, câu đó vẫn nằm trong dirtyRef. Server chuyển phiên sang SUBMITTED
      // và chấm điểm trước khi request lưu tới nơi -> mất điểm câu cuối.
      // `flush()` tự nuốt lỗi (VD 403 khi đã quá hạn) nên không chặn việc nộp.
      await flushAnswersRef.current?.()
      await apiClient.post('/exam-sessions/submit', {
        submit_type: submitType,
        session_token: state.session_token,
      })
      // Đã nộp thành công -> giữ khoá vĩnh viễn, không cho nộp lại trong
      // khoảng thời gian ngắn trước khi `navigate` unmount component.
      submittedRef.current = true
      navigate('/exam/results')
    } catch (err) {
      const status = err?.response?.status
      const message = extractErrorMessage(err, 'Không nộp được bài.')

      // 404 = phiên thi không còn tồn tại trên máy chủ (GV xoá ca, ca bị huỷ,
      // hoặc dữ liệu được dọn). Giữ người dùng lại trong phòng là vô nghĩa —
      // mọi thao tác sau đó cũng sẽ hỏng — nên dẫn họ ra khỏi phòng kèm lý do.
      if (status === 404 || status === 403) {
        setServerNotice(message)
        setTimeout(() => navigate('/exam/join', { state: { notice: message } }), 2500)
        return
      }

      // Lỗi TẠM THỜI (mất mạng, timeout, 5xx): phiên phía server vẫn có thể
      // IN_PROGRESS. Mở khoá và cho thí sinh thử lại, nếu không bài sẽ không
      // bao giờ được chấm.
      setLocked(false)
      setSubmitError(message)
      setServerNotice(message)
    } finally {
      setSubmitting(false)
      // Chỉ giữ khoá chống nộp trùng khi đã điều hướng thành công. Nếu lỗi
      // mạng, phải cho phép thử lại — nếu không, thí sinh kẹt ở màn hình
      // khoá trong khi phiên phía server vẫn IN_PROGRESS (không được chấm).
      submittingRef.current = false
    }
  }

  const handleForceSubmit = useCallback(
    (payload) => {
      setServerNotice(payload?.reason || 'Phiên thi đã kết thúc do vượt ngưỡng vi phạm.')
      setConfirmSubmit(false)
      // Khoá phiên ngay lập tức: nếu không, sau khi bị thu bài các hook giám sát
      // vẫn chạy và bộ đếm tiếp tục tăng ("Lần thứ 9/3", "Lần thứ 12/3"...)
      // trong khi server đã bỏ qua im lặng mọi vi phạm sau đó.
      setLocked(true)
      clearWarning()
      submitExam('AUTO_VIOLATION')
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [state?.session_token],
  )

  // --- Hook gốc: cấp policy + logViolation cho tất cả hook con ---
  const { policy, requireSafeBrowser, restrictedMode, logViolation } = useSecurityPolicy(
    state,
    handleForceSubmit,
  )

  // --- 7 cơ chế khoá an toàn, tất cả đều bật/tắt theo policy từ server ---
  // Chỉ kích hoạt SAU khi thí sinh bấm "Bắt đầu thi" — trước đó chưa thi.
  // Và DỪNG khi phiên đã bị thu bài (`locked`).
  const inProgress = Boolean(state) && started && !locked

  // Mức 2: cảnh báo đếm ngược yêu cầu quay lại (SRS 5.6).
  // Đặt TRƯỚC các hook khác vì useFullscreenLock / useVisibilityMonitor
  // gọi lại handleIncident.
  const { warning, remaining: warningRemaining, triggerWarning, clearWarning } =
    useViolationWarning({ policy })

  // Số lần vi phạm đã ghi nhận TRONG PHIÊN NÀY, theo từng loại.
  // Đây chỉ để HIỂN THỊ cho thí sinh — server vẫn là nguồn quyết định có nộp
  // bài hay không (client không được tự quyết, xem skills.md Quy tắc #4.3).
  // Giá trị được đồng bộ từ server trong join() — xem ngay dưới đây.
  const [strikes, setStrikes] = useState({ TAB_SWITCH: 0, FULLSCREEN_EXIT: 0 })

  // Đồng bộ bộ đếm hiển thị với server mỗi khi `state` được nạp/refresh.
  // Nếu chỉ khởi tạo useState một lần, F5 giữa chừng sẽ làm UI hiện "0/8"
  // trong khi server đã đếm 7/8 và có thể tự nộp ngay lần vi phạm kế tiếp —
  // thí sinh không hiểu vì sao bị thu bài.
  useEffect(() => {
    if (!state) return
    setStrikes({
      TAB_SWITCH: state.tab_switch_count || 0,
      FULLSCREEN_EXIT: state.fullscreen_exit_count || 0,
    })
  }, [state])
  const lastIncidentRef = useRef(0)
  // handleIncident được useCallback theo [logViolation, triggerWarning]; nếu đọc
  // `locked` trực tiếp thì phải thêm nó vào deps. Dùng ref cho gọn và để
  // handleIncident không bị tạo lại mỗi lần khoá phiên.
  const lockedRef = useRef(locked)
  lockedRef.current = locked
  // Đọc đồng bộ bộ đếm hiện tại trong handleIncident (state thì bất đồng bộ).
  const strikesRef = useRef(strikes)
  strikesRef.current = strikes
  const maxViolationsRef = useRef(0)
  maxViolationsRef.current =
    (policy?.max_tab_switch || 0) + (policy?.max_fullscreen_exit || 0)

  /**
   * Gộp mọi sự kiện rời khỏi màn thi về MỘT chỗ.
   *
   * Vì sao cần gộp: khi thí sinh Alt+Tab, trình duyệt bắn đồng thời
   * `visibilitychange` (TAB_SWITCH) và `fullscreenchange` (FULLSCREEN_EXIT).
   * Nếu để mỗi hook tự ghi vi phạm thì MỘT hành động sẽ bị tính thành hai.
   */
  const handleIncident = useCallback(
    (type, source) => {
      // Phiên đã thu bài -> không đếm nữa. Server cũng vậy (record_violation bỏ
      // qua khi status != IN_PROGRESS). Nếu không chặn ở đây, thí sinh thấy
      // bộ đếm nhảy lên vô hạn ("Lần thứ 15/3") trong khi phía giám sát đứng yên.
      if (lockedRef.current) return

      // Chống bắn trùng: blur + visibilitychange, hoặc fullscreenchange lặp.
      const now = Date.now()
      if (now - lastIncidentRef.current < 1500) return
      lastIncidentRef.current = now

      // Chặn Ở NGƯỠNG. Server cũng vậy: `record_violation` từ chối ghi khi
      // status đã là SUBMITTED, nên tổng vi phạm không bao giờ vượt quá
      // max_tab_switch + max_fullscreen_exit.
      //
      // Nếu không chặn, thí sinh thấy bộ đếm nhảy vô hạn ("23/8") trong khi
      // phía giám sát đứng yên ở 8 — hai bên không khớp, và nhìn rất vô lý.
      const cur = strikesRef.current
      const total = (cur.TAB_SWITCH || 0) + (cur.FULLSCREEN_EXIT || 0)
      if (total >= maxViolationsRef.current) return

      logViolation?.(type, { source: source || 'unknown' })
      setStrikes((prev) => ({ ...prev, [type]: (prev[type] || 0) + 1 }))
      triggerWarning(type)
    },
    [logViolation, triggerWarning],
  )

  const fullscreen = useFullscreenLock({
    enabled: inProgress && policy.require_fullscreen,
    onExit: () => handleIncident('FULLSCREEN_EXIT', 'fullscreenchange'),
  })
  useVisibilityMonitor({
    enabled: inProgress && policy.monitor_tab_switch,
    onAway: (source) => handleIncident('TAB_SWITCH', source),
  })
  useKeyboardBlock({
    // Ba cờ ĐỘC LẬP: tắt cờ nào là tắt đúng cơ chế đó, không kéo theo cờ khác.
    blockCopyPaste: inProgress && policy.block_copy_paste,
    blockDevTools: inProgress && policy.block_devtools,
    disablePrint: inProgress && policy.disable_print,
    logViolation,
  })
  useDevToolsDetector({
    enabled: inProgress && policy.detect_devtools,
    logViolation,
  })
  useNavigationLock({
    enabled: inProgress && policy.lock_navigation,
    logViolation,
  })

  // Thí sinh quay lại tab -> huỷ cảnh báo đếm ngược
  useEffect(() => {
    if (!inProgress) return undefined

    const onVisible = () => {
      if (!document.hidden) clearWarning()
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)

    return () => {
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
  }, [inProgress, clearWarning])

  /** Bấm "Bắt đầu thi": vào fullscreen (nếu bật) rồi mới bật các cơ chế khoá. */
  const handleStart = useCallback(async () => {
    // Gọi TRƯỚC khi setStarted — requestFullscreen cần user-gesture của chính
    // sự kiện click này, và không được phép gọi lại sau khi await state update.
    if (policy.require_fullscreen) {
      const ok = await fullscreen.requestFullscreen()
      if (!ok) {
        // Không vào được thì KHÔNG cho bắt đầu, thay vì im lặng bỏ qua như
        // trước đây (thí sinh tưởng đã ở chế độ bảo vệ nhưng thực ra không có).
        if (policy.allow_web_fallback) {
          setFullscreenBlocked(true)
        } else {
          setStartError(
            'Trình duyệt từ chối bật toàn màn hình. Hãy bấm F11 hoặc nút toàn màn ' +
              'màn hình trên thanh trình duyệt, rồi thử lại.',
          )
          return
        }
      }
    }
    setStarted(true)
  }, [policy.require_fullscreen, policy.allow_web_fallback, fullscreen])

  const { status: saveStatus, flush: flushAnswers } = useAutoSave({
    sessionToken: state?.session_token,
    answers,
  })
  // Nối vào ref để submitExam (khai báo phía trên) luôn dùng bản mới nhất.
  flushAnswersRef.current = flushAnswers
  submitExamRef.current = submitExam

  // --- Đồng hồ đếm ngược, bám theo mốc server trả về ---
  useEffect(() => {
    if (!state) return undefined
    // server_time là mốc chuẩn; client chỉ hiển thị (Quy tắc #4.1)
    const serverNow = new Date(state.server_time).getTime()
    const offset = Date.now() - serverNow

    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - offset - serverNow) / 1000)
      const next = Math.max(0, state.remaining_seconds - elapsed)
      setRemaining(next)

      // HẾT GIỜ -> TỰ NỘP.
      //
      // Trước đây đồng hồ chỉ dừng ở 00:00, không hề nộp bài: thí sinh vẫn
      // thấy đề, phiên phía server kẹt IN_PROGRESS và không được chấm điểm.
      // Server phía sau cũng chặn save-answer (403) nên bài coi như mất trắng.
      if (next <= 0 && !autoSubmitFiredRef.current && !lockedRef.current) {
        autoSubmitFiredRef.current = true
        clearInterval(timer)
        submitExamRef.current?.('AUTO_TIMEOUT')
      }
    }, 1000)

    return () => clearInterval(timer)
  }, [state])

  const questions = state?.questions || []
  const current = questions[currentIndex]

  // Ngưỡng vi phạm của phiên.
  //
  // Server KHÔNG ép riêng từng loại — `AnticheatService.resolve_max_violations`
  // cộng max_tab_switch + max_fullscreen_exit rồi so với TỔNG số vi phạm.
  // Nên hiển thị cũng phải theo tổng. Nếu so "số lần chuyển tab" với
  // max_tab_switch sẽ ra những thứ vô nghĩa kiểu "Lần thứ 7/5".
  const totalStrikes = (strikes.TAB_SWITCH || 0) + (strikes.FULLSCREEN_EXIT || 0)
  const maxViolations =
    (policy.max_tab_switch || 0) + (policy.max_fullscreen_exit || 0)

  const answeredIds = useMemo(
    () =>
      new Set(
        Object.entries(answers)
          .filter(([, a]) => (a.selected_option_ids?.length || 0) > 0 || a.fill_blank_text)
          .map(([qid]) => Number(qid)),
      ),
    [answers],
  )

  // --- Các trạng thái chờ ---
  //
  // THỨ TỰ RẤT QUAN TRỌNG. Phải kiểm tra `joining` và `joinError` TRƯỚC khi
  // tới `!state`, vì khi join thất bại thì `state` vẫn là null — nếu đặt
  // `!state` trước, người dùng sẽ bị kẹt ở màn "Đang tải…" vĩnh viễn và không
  // bao giờ thấy thông báo lỗi. (Đã xảy ra 1 lần trong quá trình phát triển.)
  if (joining) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500 gap-3">
        <Icon name="refresh" size={20} />
        Đang vào phòng thi…
      </div>
    )
  }

  if (sebBlocked || (requireSafeBrowser && restrictedMode)) {
    return <PolicyGate roomCode={roomCode} onRetry={join} />
  }

  if (joinError) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="max-w-md w-full card p-6 text-center">
          <Icon name="cancel" size={32} className="text-error mx-auto" />
          <h1 className="font-headline-sm font-semibold mt-3">Không vào được phòng thi</h1>
          <p className="text-slate-600 mt-2">{joinError}</p>
          <button type="button" onClick={join} className="btn-primary mt-5 w-full">
            <Icon name="refresh" size={18} />
            Thử lại
          </button>
          <button
            type="button"
            onClick={() => navigate('/exam/join')}
            className="btn-ghost w-full mt-2"
          >
            Về trang chọn phòng
          </button>
        </div>
      </div>
    )
  }

  // Chốt chặn an toàn: mọi nhánh bên dưới đều đọc `state.xxx` (room_code,
  // session_token, questions...). Guard này phải nằm SAU `joining` và
  // `joinError` — xem giải thích ở khối trên.
  if (!state) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500 gap-3">
        <Icon name="refresh" size={20} />
        Đang tải dữ liệu phòng thi…
      </div>
    )
  }

  // Màn "Sẵn sàng thi" — bước bắt buộc để trình duyệt cho phép vào fullscreen.
  if (!started) {
    const enabledMechs = [
      { key: 'require_fullscreen', icon: 'desktop_windows' },
      { key: 'block_copy_paste', icon: 'lock' },
      { key: 'block_devtools', icon: 'block' },
      { key: 'monitor_tab_switch', icon: 'visibility' },
      { key: 'lock_navigation', icon: 'shield' },
    ].filter((m) => policy[m.key])

    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-lg">
          <div className="card p-8">
            <div className="flex items-center gap-3 pb-5 border-b border-slate-100">
              <div className="w-11 h-11 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center flex-shrink-0">
                <Icon name="shield" size={22} className="text-primary" filled />
              </div>
              <div className="min-w-0">
                <h1 className="font-headline-sm font-semibold text-slate-900 truncate">
                  {state.exam_title}
                </h1>
                <span className="text-xs text-slate-500 font-mono">{state.room_code}</span>
              </div>
            </div>

            <div className="py-5 space-y-4">
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border border-slate-200 py-3">
                  <div className="text-xs text-slate-500">Thời gian</div>
                  <div className="font-semibold text-slate-800 mt-0.5">
                    {state.duration_minutes} phút
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 py-3">
                  <div className="text-xs text-slate-500">Số câu</div>
                  <div className="font-semibold text-slate-800 mt-0.5">
                    {state.questions?.length || 0}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-200 py-3">
                  <div className="text-xs text-slate-500">Chế độ</div>
                  <div className="font-semibold text-slate-800 mt-0.5 text-xs leading-6">
                    {restrictedMode ? 'Hạn chế' : 'SEB Client'}
                  </div>
                </div>
              </div>

              {enabledMechs.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-slate-700 mb-2">
                    Cơ chế bảo vệ đang bật:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {enabledMechs.map((m) => (
                      <span
                        key={m.key}
                        className="chip bg-success-50 text-success-700 border border-success/30"
                      >
                        <Icon name={m.icon} size={13} />
                        {SECURITY_MECHANISM_LABELS[m.key]?.short || m.key}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {restrictedMode && (
                <Alert variant="warning">
                  Bạn đang thi bằng trình duyệt thông thường trong khi phòng yêu cầu
                  Safe Exam Browser. Phiên thi đã được ghi nhận ở chế độ hạn chế.
                </Alert>
              )}

              {policy.require_fullscreen && (
                <Alert variant="info">
                  Khi bấm <strong>Bắt đầu thi</strong>, trình duyệt sẽ chuyển sang chế
                  độ toàn màn hình. Bạn có thể thoát toàn màn hình bằng phím{' '}
                  <kbd className="font-mono">Esc</kbd>, nhưng mỗi lần thoát sẽ bị ghi
                  nhận. Tổng số lần vi phạm được phép là{' '}
                  <strong className="font-mono">{maxViolations}</strong> (
                  {policy.max_tab_switch} lần rời tab và {policy.max_fullscreen_exit} lần
                  thoát toàn màn hình); vượt ngưỡng, hệ thống sẽ tự nộp bài.
                </Alert>
              )}

              {startError && (
                <Alert variant="error">
                  {startError}
                </Alert>
              )}

              {fullscreenBlocked && (
                <Alert variant="warning">
                  Trình duyệt không cho bật toàn màn hình. Phiên thi sẽ được ghi nhận
                  ở chế độ hạn chế.
                </Alert>
              )}
            </div>

            <div className="flex gap-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => navigate('/exam/join')}
                className="btn-ghost flex-1"
              >
                Quay lại
              </button>
              <button
                type="button"
                onClick={() => {
                  setStartError('')
                  handleStart()
                }}
                className="btn-primary flex-1 btn-lg"
              >
                <Icon name="play_arrow" size={20} />
                Bắt đầu thi
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const toggleOption = (questionId, optionId) => {
    setAnswers((prev) => {
      const key = String(questionId)
      const current = prev[key] || { selected_option_ids: [] }
      const selected = current.selected_option_ids || []
      const isMulti = questions.find((q) => q.id === questionId)?.type === 'MULTI_CHOICE'

      const nextSelected = isMulti
        ? selected.includes(optionId)
          ? selected.filter((id) => id !== optionId)
          : [...selected, optionId]
        : [optionId]

      return { ...prev, [key]: { ...current, selected_option_ids: nextSelected } }
    })
  }

  const setFillBlank = (questionId, text) => {
    setAnswers((prev) => ({
      ...prev,
      [String(questionId)]: { ...(prev[String(questionId)] || {}), fill_blank_text: text },
    }))
  }



  const securityChips = [
    { key: 'require_fullscreen', icon: 'desktop_windows' },
    { key: 'block_copy_paste', icon: 'lock' },
    { key: 'block_devtools', icon: 'block' },
    { key: 'monitor_tab_switch', icon: 'visibility' },
    { key: 'lock_navigation', icon: 'shield' },
  ]

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* Thanh trên */}
      <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/30 flex items-center justify-center flex-shrink-0">
            <Icon name="shield" size={18} className="text-primary" filled />
          </div>
          <div className="min-w-0">
            <h1 className="font-headline-sm font-semibold text-slate-800 truncate">
              {state.exam_title}
            </h1>
            <span className="text-xs text-slate-500 font-mono">{state.room_code}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {restrictedMode && (
            <Badge tone="warning" icon="warning">
              Chế độ hạn chế
            </Badge>
          )}
          <div
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${
              remaining <= 300
                ? 'bg-error-50 border-error/30 text-error'
                : 'bg-slate-50 border-slate-200 text-slate-700'
            }`}
          >
            <Icon name="timer" size={18} />
            <span className="font-mono font-semibold tabular-nums">
              {formatCountdown(remaining)}
            </span>
          </div>
          <Badge
            tone={saveStatus === 'error' ? 'error' : saveStatus === 'saving' ? 'primary' : 'success'}
            icon={saveStatus === 'error' ? 'warning' : 'cloud_done'}
          >
            {saveStatus === 'saving' ? 'Đang lưu' : saveStatus === 'error' ? 'Lỗi lưu' : 'Đã lưu'}
          </Badge>

          {/* Nút thoát luôn hiện ở thanh trên cùng — không phụ thuộc việc cuộn
              xuống đáy sidebar để tìm nút "Kết thúc & Nộp bài". */}
          <button
            type="button"
            onClick={() => setConfirmSubmit(true)}
            className="btn-danger-outline btn-sm"
            title="Thoát phòng thi và nộp bài"
          >
            <Icon name="logout" size={16} />
            Thoát & Nộp bài
          </button>
        </div>
      </header>

      {/* Dải trạng thái cơ chế bảo vệ */}
      <div className="bg-white border-b border-slate-200 px-6 py-2.5 flex items-center gap-2 flex-wrap flex-shrink-0">
        <span className="text-xs font-medium text-slate-500 mr-1">Cơ chế bảo vệ:</span>
        {securityChips.map(({ key, icon }) => (
          <span
            key={key}
            className={`chip ${
              policy[key]
                ? 'bg-success-50 text-success-700 border border-success/30'
                : 'bg-slate-100 text-slate-400 border border-slate-200'
            }`}
          >
            <Icon name={icon} size={13} />
            {SECURITY_MECHANISM_LABELS[key]?.short || key}
          </span>
        ))}
        <Badge tone={restrictedMode ? 'warning' : 'primary'} icon="security">
          {restrictedMode ? 'Web — chế độ hạn chế' : 'SEB Client đã xác thực'}
        </Badge>
      </div>

      {serverNotice && (
        <div className="px-6 pt-4">
          <div className="max-w-[1400px] mx-auto flex items-center gap-2 px-4 py-3 rounded-lg bg-warning-50 border border-warning-200 text-warning-900">
            <Icon name="warning" size={18} />
            <span>{serverNotice}</span>
            {/* Nộp thất bại vì lỗi tạm thời -> cho thử lại. Không có nút này
                thì thí sinh kẹt: server vẫn IN_PROGRESS nên bài không được chấm. */}
            {submitError && (
              <button
                type="button"
                onClick={() => submitExam(lastSubmitTypeRef.current)}
                disabled={submitting}
                className="btn-primary ml-auto flex-shrink-0"
              >
                <Icon name="refresh" size={16} />
                {submitting ? 'Đang nộp…' : 'Thử nộp lại'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Nội dung */}
      <div className="flex-1 grid grid-cols-[260px_1fr] gap-6 p-6 max-w-[1400px] w-full mx-auto overflow-hidden">
        {/* Navigator */}
        <aside className="card p-5 overflow-y-auto">
          <h2 className="font-headline-sm font-semibold text-slate-800 mb-1">
            Danh sách câu hỏi
          </h2>
          <p className="text-xs text-slate-500 mb-4">
            {answeredIds.size}/{questions.length} câu đã trả lời
          </p>

          <div className="grid grid-cols-4 gap-2">
            {questions.map((q, i) => {
              const isCurrent = i === currentIndex
              const isAnswered = answeredIds.has(q.id)
              const cls = isCurrent
                ? 'qnum-current'
                : isAnswered
                  ? 'qnum-answered'
                  : 'qnum-unanswered'
              return (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => setCurrentIndex(i)}
                  className={cls}
                  aria-current={isCurrent ? 'true' : undefined}
                >
                  {i + 1}
                </button>
              )
            })}
          </div>

          <div className="mt-5 pt-4 border-t border-slate-100 space-y-2 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-primary" /> Câu hiện tại
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-primary-50 border border-primary-100" /> Đã trả lời
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-white border border-slate-300" /> Chưa trả lời
            </div>
          </div>

          <button
            type="button"
            onClick={() => setConfirmSubmit(true)}
            className="btn-danger-outline w-full mt-6"
          >
            <Icon name="flag" size={18} />
            Kết thúc & Nộp bài
          </button>
        </aside>

        {/* Câu hỏi */}
        <main className="card p-6 overflow-y-auto">
          {current && (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-headline-sm font-semibold text-slate-800">
                  Câu {currentIndex + 1} / {questions.length}
                </h2>
                <Badge tone="neutral">{current.difficulty}</Badge>
              </div>

              <p className="text-slate-800 leading-relaxed mb-6">{current.content}</p>

              {current.type === 'FILL_BLANK' ? (
                <input
                  type="text"
                  value={answers[String(current.id)]?.fill_blank_text || ''}
                  onChange={(e) => setFillBlank(current.id, e.target.value)}
                  className="input"
                  placeholder="Nhập câu trả lời"
                />
              ) : (
                <div className="space-y-2.5">
                  {(current.options || []).map((opt) => {
                    const selected =
                      answers[String(current.id)]?.selected_option_ids || []
                    const isChecked = selected.includes(opt.id)
                    return (
                      <label
                        key={opt.id}
                        className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-colors ${
                          isChecked
                            ? 'border-primary bg-primary-50'
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <input
                          type={current.type === 'MULTI_CHOICE' ? 'checkbox' : 'radio'}
                          name={`q-${current.id}`}
                          checked={isChecked}
                          onChange={() => toggleOption(current.id, opt.id)}
                          className="mt-0.5 w-4 h-4 accent-primary"
                        />
                        <span className="text-slate-700 leading-relaxed">{opt.content}</span>
                      </label>
                    )
                  })}
                </div>
              )}

              <div className="flex justify-between mt-8 pt-5 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
                  disabled={currentIndex === 0}
                  className="btn-outline"
                >
                  <Icon name="chevron_left" size={18} />
                  Câu trước
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setCurrentIndex((i) => Math.min(questions.length - 1, i + 1))
                  }
                  disabled={currentIndex === questions.length - 1}
                  className="btn-primary"
                >
                  Câu sau
                  <Icon name="chevron_right" size={18} />
                </button>
              </div>
            </>
          )}
        </main>
      </div>

      {/* Mức 2 — cảnh báo yêu cầu quay lại trong thời gian quy định (SRS 5.6) */}
      <Modal
        open={Boolean(warning)}
        onClose={clearWarning}
        title="Cảnh báo: hành vi bị ghi nhận"
        footer={
          <button type="button" onClick={clearWarning} className="btn-primary">
            Tôi đã quay lại — Tiếp tục làm bài
          </button>
        }
      >
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-full bg-error-50 border border-error/30 flex items-center justify-center flex-shrink-0">
            <Icon name="warning" size={28} className="text-error" filled />
          </div>
          <div className="min-w-0">
            <p className="text-slate-800 leading-relaxed">
              {warning === 'FULLSCREEN_EXIT'
                ? 'Bạn đã thoát khỏi chế độ toàn màn hình.'
                : 'Hệ thống ghi nhận bạn đã rời khỏi cửa sổ thi.'}
            </p>

            {/* Đếm số lần — thông tin quan trọng nhất, đặt NGAY dưới câu mô tả.
                Trước đây modal chỉ có đồng hồ 10s nên thí sinh không biết mình
                còn bao nhiêu lần, dẫn tới cảm giác "cảnh báo vô nghĩa". */}
            <div className="mt-3 inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-error-50 border border-error/30">
              <Icon name="warning" size={18} className="text-error" />
              <span className="text-sm text-slate-700">
                Đã ghi nhận{' '}
                <strong className="font-mono text-error">{totalStrikes}</strong> /{' '}
                <strong className="font-mono">{maxViolations}</strong> lần vi phạm
              </span>
            </div>
          </div>
        </div>

        <div className="mt-5 flex items-center justify-center gap-3 py-4 rounded-lg bg-slate-50 border border-slate-200">
          <Icon name="timer" size={22} className="text-slate-500" />
          <span className="text-sm text-slate-600">Quay lại trong</span>
          <span
            className={`text-2xl font-bold font-mono tabular-nums ${
              warningRemaining <= 3 ? 'text-error' : 'text-slate-900'
            }`}
          >
            {warningRemaining}s
          </span>
        </div>

        <p className="text-xs text-slate-500 mt-4 text-center">
          {totalStrikes >= maxViolations
            ? 'Bạn đã vượt ngưỡng cho phép — hệ thống sẽ tự động nộp bài.'
            : `Còn ${maxViolations - totalStrikes} lần nữa trước khi bị ghi nhận vượt ngưỡng và tự động nộp bài.`}
        </p>
      </Modal>

      {/* Xác nhận nộp bài */}
      <Modal
        open={confirmSubmit}
        onClose={() => setConfirmSubmit(false)}
        title="Xác nhận nộp bài"
        footer={
          <>
            <button type="button" onClick={() => setConfirmSubmit(false)} className="btn-ghost">
              Tiếp tục làm bài
            </button>
            <button
              type="button"
              onClick={() => submitExam('MANUAL')}
              disabled={submitting}
              className="btn-danger"
            >
              {submitting ? 'Đang nộp…' : 'Nộp bài'}
            </button>
          </>
        }
      >
        <p className="text-slate-700">
          Bạn đã trả lời <strong>{answeredIds.size}</strong> trên tổng số{' '}
          <strong>{questions.length}</strong> câu hỏi.
        </p>
        {answeredIds.size < questions.length && (
          <p className="mt-2 text-warning-700 text-sm">
            Vẫn còn {questions.length - answeredIds.size} câu chưa trả lời. Sau khi
            nộp bài bạn không thể sửa lại.
          </p>
        )}
      </Modal>
    </div>
  )
}
