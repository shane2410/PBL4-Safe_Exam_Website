import { useId } from 'react'

/** Input có nhãn + helper text + trạng thái lỗi. */
export default function Input({
  label,
  helper,
  error,
  type = 'text',
  value,
  onChange,
  placeholder,
  disabled = false,
  required = false,
  id: providedId,
  className = '',
  ...rest
}) {
  const generatedId = useId()
  const id = providedId || generatedId
  const describedBy = error ? `${id}-err` : helper ? `${id}-help` : undefined

  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="label">
          {label}
          {required && <span className="text-error ml-0.5">*</span>}
        </label>
      )}
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`input ${error ? 'input-error' : ''} ${
          disabled ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : ''
        }`}
        {...rest}
      />
      {error ? (
        <p id={`${id}-err`} className="helper-error">
          {error}
        </p>
      ) : (
        helper && (
          <p id={`${id}-help`} className="helper">
            {helper}
          </p>
        )
      )}
    </div>
  )
}
