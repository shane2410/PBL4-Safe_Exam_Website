import { Component } from 'react'
import Icon from './Icon'

/**
 * Bắt lỗi runtime khi render.
 *
 * Không có ErrorBoundary, một lỗi nhỏ (đọc thuộc tính của null chẳng hạn) sẽ làm
 * React dỡ cả cây component và người dùng chỉ thấy TRANG TRẮNG, không biết vì sao.
 * Lớp này biến lỗi thành thông báo đọc được + đường thoát.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Ghi ra console để còn tra khi demo; không gửi đi đâu để tránh rò dữ liệu
    console.error('[ErrorBoundary]', error, info?.componentStack)
  }

  handleReset = () => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-md">
          <div className="card p-8 text-center">
            <Icon name="cancel" size={40} className="text-error mx-auto" />
            <h1 className="font-headline-sm font-semibold text-slate-900 mt-4">
              Đã xảy ra lỗi
            </h1>
            <p className="text-slate-600 mt-2 text-sm leading-relaxed">
              Giao diện gặp lỗi khi hiển thị. Bạn có thể tải lại trang — dữ liệu bài
              làm của bạn đã được lưu trên máy chủ và không bị mất.
            </p>
            <details className="mt-4 text-left">
              <summary className="text-xs text-slate-400 cursor-pointer select-none">
                Chi tiết lỗi (dành cho kỹ thuật)
              </summary>
              <pre className="mt-2 p-3 rounded-lg bg-slate-900 text-slate-100 text-xs overflow-auto max-h-40 whitespace-pre-wrap">
                {String(this.state.error?.message || this.state.error)}
              </pre>
            </details>
            <button
              type="button"
              onClick={this.handleReset}
              className="btn-primary w-full mt-6"
            >
              <Icon name="refresh" size={18} />
              Tải lại trang
            </button>
          </div>
        </div>
      </div>
    )
  }
}
