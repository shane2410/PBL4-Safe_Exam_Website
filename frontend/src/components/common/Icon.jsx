/**
 * Icon dùng chung, render từ Google Material Symbols (font có sẵn trong index.html).
 * Toàn bộ icon trong dự án đi qua component này để không phải thêm thư viện.
 */
const ICON_MAP = {
  shield: '\u{1F6E1}',
  dashboard: 'space_dashboard',
  group: 'group',
  settings: 'settings',
  assignment: 'assignment',
  school: 'school',
  description: 'description',
  event: 'event',
  query_stats: 'query_stats',
  logout: 'logout',
  login: 'login',
  security: 'security',
  tune: 'tune',
  warning: 'warning',
  info: 'info',
  check_circle: 'check_circle',
  cancel: 'cancel',
  timer: 'timer',
  cloud_done: 'cloud_done',
  lock: 'lock',
  desktop_windows: 'desktop_windows',
  laptop_mac: 'laptop_mac',
  terminal: 'terminal',
  chevron_left: 'chevron_left',
  chevron_right: 'chevron_right',
  refresh: 'refresh',
  download: 'download',
  visibility: 'visibility',
  visibility_off: 'visibility_off',
  block: 'block',
  play_arrow: 'play_arrow',
  add: 'add',
  edit: 'edit',
  delete: 'delete',
  check: 'check',
  close: 'close',
  picture_as_pdf: 'picture_as_pdf',
  table_view: 'table_view',
  people_alt: 'people_alt',
  schedule: 'schedule',
  monitoring: 'monitoring',
  history: 'history',
  trending_up: 'trending_up',
  trending_down: 'trending_down',
  expand_more: 'expand_more',
  person_add: 'person_add',
  lock_reset: 'lock_reset',
  lock_open: 'lock_open',
  manage_accounts: 'manage_accounts',
  upload_file: 'upload_file',
  keyboard_arrow_up: 'keyboard_arrow_up',
  keyboard_arrow_down: 'keyboard_arrow_down',
  flag: 'flag',
}

export default function Icon({ name, size = 20, filled = false, className = '' }) {
  const symbol = ICON_MAP[name]
  if (!symbol) {
    console.warn(`Icon không tồn tại trong ICON_MAP: ${name}`)
    return null
  }
  return (
    <span
      className={`material-symbols-outlined ${filled ? 'material-symbols-fill' : ''} ${className}`}
      style={{ fontSize: `${size}px`, width: `${size}px`, height: `${size}px` }}
      aria-hidden="true"
    >
      {symbol}
    </span>
  )
}
