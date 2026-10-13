import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import Icon from './Icon'

/** Modal nền mờ, dùng cho xác nhận nộp bài, cảnh báo mức 2... */
export default function Modal({ open, onClose, title, children, footer, maxWidth = 'max-w-lg' }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="absolute inset-0 bg-black/45"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className={`relative w-full ${maxWidth} bg-white rounded-lg shadow-large`}>
        {title && (
          <div className="flex items-center gap-2 px-6 py-4 border-b border-slate-200">
            <Icon name="info" size={20} className="text-primary" />
            <h3 className="font-headline-sm font-semibold text-slate-800">{title}</h3>
          </div>
        )}
        <div className="px-6 py-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50 rounded-b-lg">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
