import Icon from './Icon'

/** Bảng báo lỗi / thông báo dạng banner (info, success, warning, error). */
const VARIANTS = {
  info: { wrap: 'bg-primary-50 border-primary-100 text-primary-800', icon: 'info', iconColor: 'text-primary' },
  success: { wrap: 'bg-success-50 border-success/30 text-success-700', icon: 'check_circle', iconColor: 'text-success' },
  warning: { wrap: 'bg-warning-50 border-warning-200 text-warning-900', icon: 'warning', iconColor: 'text-warning-700' },
  error: { wrap: 'bg-error-50 border-error/30 text-error-700', icon: 'cancel', iconColor: 'text-error' },
}

export default function Alert({ variant = 'info', title, children, className = '' }) {
  const v = VARIANTS[variant] || VARIANTS.info
  return (
    <div className={`flex items-start gap-3 p-3.5 rounded-lg border ${v.wrap} ${className}`} role="alert">
      <Icon name={v.icon} size={20} className={`${v.iconColor} flex-shrink-0 mt-px`} />
      <div className="min-w-0 text-body-md leading-relaxed">
        {title && <strong className="block font-semibold mb-0.5">{title}</strong>}
        {children}
      </div>
    </div>
  )
}
