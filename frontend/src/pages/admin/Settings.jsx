import { useEffect, useState } from 'react'
import Card from '../../components/common/Card'
import Toggle from '../../components/common/Toggle'
import Input from '../../components/common/Input'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import policyService, {
  DEFAULT_SECURITY_CONFIG,
  SECURITY_MECHANISM_LABELS,
  TOGGLE_MECHANISMS,
} from '../../services/policyService'
import { extractErrorMessage } from '../../services/apiClient'

/**
 * Trang Cấu hình hệ thống (Admin).
 *
 * Đây là nơi GV/Admin bật cờ "only through safe exam browser" ở CẤP HỆ THỐNG.
 * Cờ cấp đề nằm ở trang ExamEditor. Hiệu lực thật sự = cờ đề AND cờ hệ thống.
 *
 * Mọi thay đổi đều đi qua API và được server kiểm tra lại — UI chỉ là lớp trình bày.
 */
export default function Settings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [requireSafeBrowser, setRequireSafeBrowser] = useState(false)
  const [sebConfig, setSebConfig] = useState(null)
  const [defaultPolicy, setDefaultPolicy] = useState(DEFAULT_SECURITY_CONFIG)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const data = await policyService.getSystemSettings()
        if (cancelled) return
        setRequireSafeBrowser(Boolean(data.require_safe_browser_global))
        setSebConfig(data.seb_client_config)
        setDefaultPolicy({ ...DEFAULT_SECURITY_CONFIG, ...data.default_security_config })
      } catch (err) {
        if (!cancelled) setError(extractErrorMessage(err, 'Không tải được cấu hình hệ thống.'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  const toggleGlobal = async (value) => {
    setError('')
    setSuccess('')
    const previous = requireSafeBrowser
    setRequireSafeBrowser(value) // cập nhật UI ngay cho phản hồi nhanh
    try {
      await policyService.setRequireSafeBrowserGlobal(value)
      setSuccess(
        value
          ? 'Đã bật yêu cầu Safe Exam Browser. Các đề thi có cờ bắt buộc sẽ chỉ nhận SEB Client.'
          : 'Đã tắt yêu cầu Safe Exam Browser. Mọi thí sinh có thể thi bằng trình duyệt web.',
      )
    } catch (err) {
      setRequireSafeBrowser(previous) // hoàn tác nếu server từ chối
      setError(extractErrorMessage(err, 'Không cập nhật được cấu hình.'))
    }
  }

  const saveSebConfig = async () => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await policyService.setSebClientConfig(sebConfig)
      setSuccess('Đã lưu cấu hình SEB Client.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Không lưu được cấu hình SEB Client.'))
    } finally {
      setSaving(false)
    }
  }

  const saveDefaultPolicy = async () => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await policyService.setDefaultSecurityConfig(defaultPolicy)
      setSuccess('Đã lưu cấu hình khoá an toàn mặc định.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Không lưu được cấu hình khoá an toàn.'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-3 text-slate-500">
        <Icon name="refresh" size={20} />
        Đang tải cấu hình…
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto space-y-6 pb-20">
        {/* Tiêu đề trang */}
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
              Cấu hình hệ thống
            </h1>
            <span className="chip bg-primary-50 text-primary-700 border border-primary-100">
              Môi trường Thi Trực tuyến
            </span>
          </div>
          <p className="text-slate-600 max-w-3xl">
            Thiết lập các tham số bảo mật, tích hợp trình duyệt chuyên dụng và chính sách
            phòng thi trực tuyến.
          </p>
        </div>

        {error && <Alert variant="error">{error}</Alert>}
        {success && <Alert variant="success">{success}</Alert>}

        {/* CARD 1 — Cờ bắt buộc Safe Exam Browser */}
        <Card accent icon="security" title="Yêu cầu Safe Exam Browser">
          <div className="flex items-start justify-between gap-6">
            <p className="text-slate-600 leading-relaxed">
              Khi bật, đề thi có cờ bắt buộc sẽ chỉ cho phép thí sinh thi qua ứng dụng
              Safe Exam Browser Client. Thí sinh dùng trình duyệt web sẽ bị ghi nhận
              vi phạm và gán điểm rủi ro.
            </p>
            <div className="flex-shrink-0 pt-1">
              <Toggle
                checked={requireSafeBrowser}
                onChange={toggleGlobal}
                label="Bật yêu cầu Safe Exam Browser"
              />
            </div>
          </div>

          <Alert variant="warning" className="mt-5">
            <strong>Giới hạn kỹ thuật:</strong> đây là cơ chế <em>răn đe và ghi nhận
            bằng chứng</em>, không phải ngăn chặn tuyệt đối. Thí sinh vẫn có thể dùng
            trình duyệt web, nhưng phiên thi đó sẽ bị đánh dấu và ghi vào nhật ký phục
            tra. Giá trị thật của cờ nằm ở việc hệ thống phân biệt được phiên thi hợp
            lệ với phiên thi không qua kiểm chứng.
          </Alert>
        </Card>

        {/* CARD 2 — Cấu hình SEB Client */}
        <Card icon="tune" title="Cấu hình SEB Client">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Input
              label="Phiên bản tối thiểu"
              value={sebConfig?.min_version || ''}
              onChange={(v) => setSebConfig((c) => ({ ...c, min_version: v }))}
              placeholder="1.0.0"
              helper="Các phiên bản cũ hơn sẽ bị từ chối vào phòng thi."
            />
            <Input
              label="Khoảng thời gian heartbeat (giây)"
              type="number"
              value={sebConfig?.heartbeat_interval ?? ''}
              onChange={(v) =>
                setSebConfig((c) => ({ ...c, heartbeat_interval: Number(v) || 0 }))
              }
              helper="Client gửi tín hiệu sống định kỳ. Quá ngưỡng này không có tín hiệu sẽ bị coi là mất kết nối."
            />
            <Input
              label="Ngưỡng mất kết nối (giây)"
              type="number"
              value={sebConfig?.heartbeat_timeout ?? ''}
              onChange={(v) =>
                setSebConfig((c) => ({ ...c, heartbeat_timeout: Number(v) || 0 }))
              }
              helper="Sau thời gian này không nhận được heartbeat, server đánh dấu phiên thi mất kết nối."
            />
            <div className="flex items-end pb-1">
              <Toggle
                checked={Boolean(sebConfig?.attestation_required)}
                onChange={(v) => setSebConfig((c) => ({ ...c, attestation_required: v }))}
                label="Bắt buộc challenge-response HMAC"
                description="Bật khi đã phát hành SEB Client; client cũ chưa có cơ chế ký sẽ không vào được phòng thi."
              />
            </div>
          </div>

          <div className="flex justify-end mt-6">
            <button type="button" onClick={saveSebConfig} disabled={saving} className="btn-primary">
              {saving ? 'Đang lưu…' : 'Lưu cấu hình SEB Client'}
            </button>
          </div>
        </Card>

        {/* CARD 3 — Cấu hình khoá an toàn mặc định */}
        <Card
          icon="lock"
          title="Cấu hình khoá an toàn mặc định"
          action={
            <span className="text-xs text-slate-500">Áp dụng cho đề chưa cấu hình riêng</span>
          }
        >
          <div className="space-y-4 divide-y divide-slate-100">
            {TOGGLE_MECHANISMS.map((key) => (
              <div key={key} className="py-3 first:pt-0 last:pb-0">
                <Toggle
                  checked={Boolean(defaultPolicy[key])}
                  onChange={(v) => setDefaultPolicy((p) => ({ ...p, [key]: v }))}
                  label={SECURITY_MECHANISM_LABELS[key].label}
                  description={SECURITY_MECHANISM_LABELS[key].description}
                />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 pt-5 border-t border-slate-100">
            <Input
              label="Ngưỡng chuyển tab tối đa"
              type="number"
              value={defaultPolicy.max_tab_switch}
              onChange={(v) =>
                setDefaultPolicy((p) => ({ ...p, max_tab_switch: Number(v) || 0 }))
              }
              helper="Vượt ngưỡng sẽ kích hoạt xử lý mức 3."
            />
            <Input
              label="Ngưỡng thoát toàn màn hình tối đa"
              type="number"
              value={defaultPolicy.max_fullscreen_exit}
              onChange={(v) =>
                setDefaultPolicy((p) => ({ ...p, max_fullscreen_exit: Number(v) || 0 }))
              }
            />
            <Input
              label="Thời gian đếm ngược yêu cầu quay lại (giây)"
              type="number"
              value={defaultPolicy.warn_countdown_seconds}
              onChange={(v) =>
                setDefaultPolicy((p) => ({ ...p, warn_countdown_seconds: Number(v) || 0 }))
              }
            />
            <div className="flex items-end pb-1">
              <Toggle
                checked={defaultPolicy.auto_submit_on_threshold}
                onChange={(v) =>
                  setDefaultPolicy((p) => ({ ...p, auto_submit_on_threshold: v }))
                }
                label="Tự động nộp bài khi vượt ngưỡng"
                description="Server sẽ tự nộp bài và ghi nhận đầy đủ log làm căn cứ phúc tra."
              />
            </div>
          </div>

          <div className="flex justify-end mt-6">
            <button
              type="button"
              onClick={saveDefaultPolicy}
              disabled={saving}
              className="btn-primary"
            >
              {saving ? 'Đang lưu…' : 'Lưu cấu hình khoá an toàn'}
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}
