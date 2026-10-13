import Icon from './Icon'

/** Badge trạng thái nhỏ (success / warning / error / primary / neutral). */
const TONES = {
  success: 'bg-success-50 text-success-700 border border-success/30',
  warning: 'bg-warning-50 text-warning-700 border border-warning-200',
  error: 'bg-error-50 text-error-700 border border-error/30',
  primary: 'bg-primary-50 text-primary-700 border border-primary-100',
  neutral: 'bg-slate-100 text-slate-600 border border-slate-200',
}

export default function Badge({ tone = 'neutral', icon, children, className = '' }) {
  return (
    <span className={`chip ${TONES[tone]} ${className}`}>
      {icon && <Icon name={icon} size={14} />}
      {children}
    </span>
  )
}
