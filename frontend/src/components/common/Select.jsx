import { useId } from 'react'

/** Select có nhãn + helper, dùng cho Môn học, Phiên bản SEB... */
export default function Select({
  label,
  helper,
  error,
  value,
  onChange,
  options = [],
  disabled = false,
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
        </label>
      )}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`input ${error ? 'input-error' : ''} cursor-pointer`}
        {...rest}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
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
