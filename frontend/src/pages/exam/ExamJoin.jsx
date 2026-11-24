import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Icon from '../../components/common/Icon'
import Alert from '../../components/common/Alert'
import Card from '../../components/common/Card'

/** Trang thí sinh chọn phòng thi trước khi vào ExamRoom. */
export default function ExamJoin() {
  const [roomCode, setRoomCode] = useState('')
  const [notice, setNotice] = useState('')
  const navigate = useNavigate()
  const location = useLocation()

  // Hiện lý do bị đưa ra khỏi phòng thi (ví dụ phiên không còn tồn tại)
  useEffect(() => {
    if (location.state?.notice) setNotice(location.state.notice)
  }, [location.state])

  const handleSubmit = (e) => {
    e.preventDefault()
    const code = roomCode.trim()
    if (!code) return

    const roomUrl = `/exam/room?room=${encodeURIComponent(code)}`
    if (new URLSearchParams(location.search).get('embedded') === '1') {
      navigate(`${roomUrl}&embedded=1`)
      return
    }

    // Open synchronously during the submit gesture. Browsers can ignore the
    // popup hint, or block popups entirely; in that case don't strand the user.
    const examWindow = window.open('', '_blank', 'popup')
    if (!examWindow) {
      navigate(roomUrl)
      return
    }
    examWindow.opener = null
    examWindow.location.replace(new URL(roomUrl, window.location.origin).href)
  }

  return (
    <div className="p-8">
      <div className="max-w-xl mx-auto space-y-6">
        <div className="space-y-1">
          <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
            Vào phòng thi
          </h1>
          <p className="text-slate-600">
            Nhập mã phòng do giảng viên cung cấp để bắt đầu bài thi.
          </p>
        </div>

        {notice && (
          <Alert variant="error" className="mb-6">
            {notice}
          </Alert>
        )}

        <Card icon="lock" title="Mã phòng thi">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="room-code" className="label">
                Mã phòng thi
              </label>
              <input
                id="room-code"
                value={roomCode}
                onChange={(e) => setRoomCode(e.target.value)}
                placeholder="Ví dụ: PBL4-EXAM-01"
                className="input font-mono"
                required
              />
              <p className="helper">Mã phòng không phân biệt hoa thường.</p>
            </div>

            <button type="submit" className="btn-primary w-full">
              <Icon name="login" size={18} />
              Vào phòng thi
            </button>
          </form>
        </Card>

        <Alert variant="info" title="Lưu ý về thiết bị">
          Một số phòng thi yêu cầu ứng dụng Safe Exam Browser Client. Nếu phòng bị
          chặn, hệ thống sẽ hướng dẫn bạn cách cài đặt.
        </Alert>
      </div>
    </div>
  )
}
