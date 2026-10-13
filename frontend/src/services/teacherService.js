import apiClient from './apiClient'

/** Service cho module giáo viên: câu hỏi, đề thi, ca thi, báo cáo, giám sát. */
export const teacherService = {
  // --- Môn học ---
  async getSubjects() {
    const { data } = await apiClient.get('/questions/subjects')
    return data
  },
  async createSubject(payload) {
    const { data } = await apiClient.post('/questions/subjects', payload)
    return data
  },

  // --- Ngân hàng câu hỏi ---
  async getQuestions(params = {}) {
    const { data } = await apiClient.get('/questions', { params })
    return data
  },
  async getQuestion(id) {
    const { data } = await apiClient.get(`/questions/${id}`)
    return data
  },
  async createQuestion(payload) {
    const { data } = await apiClient.post('/questions', payload)
    return data
  },
  async updateQuestion(id, payload) {
    const { data } = await apiClient.put(`/questions/${id}`, payload)
    return data
  },
  async deleteQuestion(id) {
    const { data } = await apiClient.delete(`/questions/${id}`)
    return data
  },

  // --- Đề thi ---
  async getExams(params = {}) {
    const { data } = await apiClient.get('/exams', { params })
    return data
  },
  async getExam(id) {
    const { data } = await apiClient.get(`/exams/${id}`)
    return data
  },
  async createExam(payload) {
    const { data } = await apiClient.post('/exams', payload)
    return data
  },
  async updateExam(id, payload) {
    const { data } = await apiClient.put(`/exams/${id}`, payload)
    return data
  },
  async deleteExam(id) {
    const { data } = await apiClient.delete(`/exams/${id}`)
    return data
  },

  // --- Ca thi ---
  async getSchedules(status) {
    const { data } = await apiClient.get('/exams/schedules/list', {
      params: status ? { status } : undefined,
    })
    return data
  },
  async createSchedule(payload) {
    const { data } = await apiClient.post('/exams/schedules', payload)
    return data
  },
  async updateSchedule(id, payload) {
    const { data } = await apiClient.put(`/exams/schedules/${id}`, payload)
    return data
  },

  // --- Nhập câu hỏi từ file .docx ---
  /** Bước 1: đọc thử file. Chưa ghi gì vào CSDL — trả về kết quả + danh sách lỗi. */
  async previewImport(file, subjectId) {
    const form = new FormData()
    form.append('file', file)
    form.append('subject_id', String(subjectId))
    // Đặt Content-Type thủ công để axios không ghi đè boundary của multipart
    const { data } = await apiClient.post('/questions/import/preview', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  /** Bước 2: ghi các câu hỏi đã duyệt vào ngân hàng. */
  async commitImport(previewToken, subjectId) {
    const { data } = await apiClient.post('/questions/import/commit', {
      preview_token: previewToken,
      subject_id: subjectId,
    })
    return data
  },

  /** Tải file .docx mẫu về máy GV. */
  async downloadTemplate() {
    const response = await fetch('/api/questions/import/template', {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (!response.ok) throw new Error('Không tải được file mẫu')

    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = 'Mau_Import_Cau_Hoi.docx'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  },

  // --- Báo cáo ---
  async getScheduleStatistics(scheduleId) {
    const { data } = await apiClient.get(`/reports/schedules/${scheduleId}/statistics`)
    return data
  },
  async getSessionViolations(sessionId) {
    const { data } = await apiClient.get(`/reports/sessions/${sessionId}/violations`)
    return data
  },

  /**
   * Tải file báo cáo. Dùng fetch + blob thay vì window.open vì endpoint cần
   * Authorization header — mở bằng thẻ <a> sẽ không kèm token và bị 401.
   */
  async downloadReport(scheduleId, format) {
    const url = `/api/reports/schedules/${scheduleId}/export-${format}`
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
    })
    if (!response.ok) throw new Error('Không tải được báo cáo')

    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="?([^";]+)"?/)
    const filename = match ? match[1] : `BaoCaoThi_${scheduleId}.${format}`

    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(objectUrl)
  },
}

export default teacherService
