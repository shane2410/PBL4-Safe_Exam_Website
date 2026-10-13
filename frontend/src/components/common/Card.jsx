import Icon from './Icon'

/** Card tiêu đề dùng chung cho các trang quản trị. */
export default function Card({ icon, title, action, accent = false, children, className = '' }) {
  return (
    <section
      className={`card p-6 ${
        accent ? 'border-l-4 border-l-primary' : ''
      } ${className}`}
    >
      {(title || action) && (
        <header
          className={`flex items-center justify-between gap-4 ${
            accent ? '' : 'border-b border-slate-100 pb-3 -mt-1'
          }`}
        >
          <div className="flex items-center gap-2 min-w-0">
            {icon && <Icon name={icon} size={20} className="text-primary flex-shrink-0" />}
            <h2 className="font-headline-sm font-semibold text-slate-800 truncate">{title}</h2>
          </div>
          {action}
        </header>
      )}
      <div className={title || action ? 'mt-5' : ''}>{children}</div>
    </section>
  )
}
