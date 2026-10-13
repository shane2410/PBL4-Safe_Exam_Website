import { useId } from 'react'

/**
 * Toggle switch (phong cách Material).
 * Dùng cho mọi công tắc bật/tắt trong hệ thống: cờ require_safe_browser,
 * từng cơ chế khoá an toàn trong security config.
 */
export default function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  accentColor = 'bg-success',
  id: providedId,
}) {
  const generatedId = useId()
  const id = providedId || generatedId
  const describedBy = description ? `${id}-desc` : undefined

  return (
    <div className="flex items-start justify-between gap-4">
      {(label || description) && (
        <div className="min-w-0">
          {label && (
            <label
              htmlFor={id}
              className={`block text-body-md-medium text-slate-800 ${
                disabled ? 'opacity-60' : 'cursor-pointer'
              }`}
            >
              {label}
            </label>
          )}
          {description && (
            <p id={describedBy} className="helper">
              {description}
            </p>
          )}
        </div>
      )}

      <label
        htmlFor={id}
        aria-describedby={describedBy}
        className={`relative inline-flex items-center flex-shrink-0 ${
          disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
        }`}
      >
        <input
          id={id}
          type="checkbox"
          className="sr-only peer"
          checked={checked}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        <div
          className={`w-11 h-6 bg-slate-300 rounded-full peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary-300
            peer-checked:after:translate-x-5 peer-checked:after:border-white
            after:content-[''] after:absolute after:top-[2px] after:left-[2px]
            after:bg-white after:border-slate-300 after:border after:rounded-full
            after:h-5 after:w-5 after:transition-all
            ${checked ? accentColor : ''}`}
        />
      </label>
    </div>
  )
}
