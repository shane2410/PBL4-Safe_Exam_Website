import { useCallback, useEffect, useRef, useState } from 'react'
import apiClient from '../../../services/apiClient'

/**
 * Tự lưu đáp án (debounce 1.5s) và lưu ngay khi thí sinh rời trang.
 *
 * Ghi chú thời gian (skills.md Quy tắc #4.1): client gửi `client_timestamp` chỉ để
 * đối chiếu. Server TỰ chặn lưu đáp án sau khi hết giờ — kể cả khi gọi API
 * trực tiếp bằng curl, không chỉ khi đồng hồ trên UI đã về 0.
 */
const AUTOSAVE_DELAY_MS = 1500

export function useAutoSave({ sessionToken, answers }) {
  const [status, setStatus] = useState('idle') // idle | saving | saved | error

  const dirtyRef = useRef(new Set())
  const timerRef = useRef(null)
  const lastSavedRef = useRef('{}')

  const flush = useCallback(async () => {
    const pending = Array.from(dirtyRef.current)
    if (!pending.length || !sessionToken) return

    setStatus('saving')
    try {
      // Gửi tuần tự: tránh nhiều request cùng lúc trên cùng một phiên thi
      for (const questionId of pending) {
        const answer = answers[String(questionId)]
        if (!answer) {
          dirtyRef.current.delete(questionId)
          continue
        }
        await apiClient.post('/exam-sessions/save-answer', {
          question_id: Number(questionId),
          selected_option_ids: answer.selected_option_ids || [],
          fill_blank_text: answer.fill_blank_text || '',
          client_timestamp: new Date().toISOString(),
          session_token: sessionToken,
        })
        dirtyRef.current.delete(questionId)
      }
      lastSavedRef.current = JSON.stringify(answers)
      setStatus('saved')
    } catch {
      // Giữ nguyên các câu chưa lưu được để thử lại ở vòng kế tiếp
      setStatus('error')
    }
  }, [answers, sessionToken])

  // So sánh snapshot để biết câu nào vừa thay đổi, rồi hẹn giờ lưu
  useEffect(() => {
    const snapshot = JSON.stringify(answers)
    if (snapshot === lastSavedRef.current) return undefined

    let prev = {}
    try {
      prev = JSON.parse(lastSavedRef.current || '{}')
    } catch {
      prev = {}
    }

    for (const questionId of Object.keys(answers)) {
      if (JSON.stringify(prev[questionId]) === JSON.stringify(answers[questionId])) continue
      dirtyRef.current.add(questionId)
    }

    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(flush, AUTOSAVE_DELAY_MS)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [answers, flush])

  // Lưu ngay khi đóng tab. Dùng keepalive của fetch vì axios không gửi được
  // request kèm Authorization header trong giai đoạn unload.
  useEffect(() => {
    if (!sessionToken) return undefined

    const onUnload = () => {
      if (!dirtyRef.current.size) return
      const token = localStorage.getItem('access_token')
      if (!token) return

      for (const questionId of dirtyRef.current) {
        const answer = answers[String(questionId)]
        if (!answer) continue
        fetch('/api/exam-sessions/save-answer', {
          method: 'POST',
          keepalive: true,
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            question_id: Number(questionId),
            selected_option_ids: answer.selected_option_ids || [],
            fill_blank_text: answer.fill_blank_text || '',
            session_token: sessionToken,
          }),
        }).catch(() => {})
      }
    }

    window.addEventListener('beforeunload', onUnload)
    return () => window.removeEventListener('beforeunload', onUnload)
  }, [answers, sessionToken])

  return { status, flush }
}

export default useAutoSave
