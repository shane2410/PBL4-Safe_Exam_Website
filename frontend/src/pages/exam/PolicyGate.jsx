import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'

/**
 * Màn hình chặn khi đề thi bắt buộc Safe Exam Browser mà thí sinh đang dùng web.
 *
 * Thiết kế theo quyết định đã chốt: KHÔNG chặn cứng, mà cảnh báo + hướng dẫn
 * để thí sinh chuyển sang SEB Client. Phiên thi vẫn được tạo ở chế độ hạn chế và
 * đã ghi log UNAUTHORIZED_CLIENT phục vụ phục tra (xem docs/PLAN.md mục 0.4).
 *
 * @param {object}   props
 * @param {string}   props.roomCode   Mã phòng thi để thí sinh nhập lại ở client
 * @param {Function} props.onRetry     Gọi lại join để kiểm tra client đã xác thực
 * @param {boolean}  props.canFallback GV có cho phép thi bằng web chế độ hạn chế
 * @param {Function} props.onAcceptFallback
 */
const DOWNLOADS = [
  { os: 'Windows', icon: 'desktop_windows', ext: '.exe' },
  { os: 'macOS', icon: 'laptop_mac', ext: '.dmg' },
  { os: 'Linux', icon: 'terminal', ext: '.AppImage' },
]

export default function PolicyGate({
  roomCode,
  onRetry,
  canFallback = false,
  onAcceptFallback,
  reason,
}) {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-[520px] bg-white rounded-lg shadow-medium border border-slate-200">
        {/* Cảnh báo */}
        <div className="px-8 pt-8 pb-2 text-center">
          <div className="w-16 h-16 mx-auto rounded-full bg-warning-50 border border-warning-200 flex items-center justify-center">
            <Icon name="warning" size={32} className="text-warning-700" filled />
          </div>
          <h1 className="font-headline-lg font-bold text-slate-900 mt-4">
            Đề thi này yêu cầu Safe Exam Browser
          </h1>
          <p className="text-slate-600 mt-2 leading-relaxed">
            Phòng thi này chỉ chấp nhận thí sinh sử dụng ứng dụng Safe Exam Browser
            Client để bảo đảm tính liên tục của kỳ thi. Bạn đang truy cập bằng trình
            duyệt thông thường.
          </p>
        </div>

        <div className="px-8 pb-6 space-y-6">
          {reason && <Alert variant="warning">{reason}</Alert>}

          <Alert variant="info">
            Hành động của bạn đã được ghi nhận vào nhật ký giám sát của phiên thi
            {roomCode ? ` (phòng ${roomCode})` : ''}.
          </Alert>

          {/* Hướng dẫn 3 bước */}
          <ol className="space-y-3">
            {[
              'Tải ứng dụng Safe Exam Browser Client',
              'Mở ứng dụng và đăng nhập tài khoản của bạn',
              `Nhập mã phòng thi ${roomCode || '...'} để vào phòng`,
            ].map((text, i) => (
              <li key={text} className="flex items-start gap-3">
                <span className="w-6 h-6 rounded-full bg-primary text-white text-xs font-semibold flex items-center justify-center flex-shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <span className="text-slate-700 leading-relaxed">{text}</span>
              </li>
            ))}
          </ol>

          {/* Nút tải theo hệ điều hành */}
          <div className="grid grid-cols-3 gap-3">
            {DOWNLOADS.map((d) => (
              <button
                key={d.os}
                type="button"
                className="flex flex-col items-center gap-2 p-3 rounded-lg border border-slate-200 hover:border-primary hover:bg-primary-50 transition-colors"
                // TODO(Phase 1): thay bằng URL phát hành thật khi có SEB Client
                title={`Tải cho ${d.os} (${d.ext}) — sẽ khả dụng ở Phase 1`}
              >
                <Icon name={d.icon} size={22} className="text-slate-600" />
                <span className="text-xs font-medium text-slate-700">{d.os}</span>
                <span className="text-[10px] text-slate-400 font-mono">{d.ext}</span>
              </button>
            ))}
          </div>

          <p className="text-xs text-slate-400 text-center">
            SEB Client dự kiến khả dụng ở Phase 1 của đồ án.
          </p>

          {/* Hành động */}
          <div className="flex flex-col gap-3 pt-2 border-t border-slate-100">
            <button type="button" onClick={onRetry} className="btn-outline w-full">
              <Icon name="refresh" size={18} />
              Tôi đã cài SEB Client — Thử lại
            </button>

            {canFallback && (
              <button
                type="button"
                onClick={onAcceptFallback}
                className="w-full text-center text-sm text-slate-500 hover:text-primary py-2 transition-colors"
              >
                Thi bằng trình duyệt với chế độ hạn chế
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
