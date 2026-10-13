import { useCallback, useEffect, useState } from 'react'
import Card from '../../components/common/Card'
import Badge from '../../components/common/Badge'
import Input from '../../components/common/Input'
import Select from '../../components/common/Select'
import Modal from '../../components/common/Modal'
import Alert from '../../components/common/Alert'
import Icon from '../../components/common/Icon'
import apiClient, { extractErrorMessage } from '../../services/apiClient'

const ROLES = [
  { value: 'ADMIN', label: 'Quản trị viên' },
  { value: 'TEACHER', label: 'Giảng viên' },
  { value: 'STUDENT', label: 'Sinh viên' },
]

const ROLE_TONE = { ADMIN: 'error', TEACHER: 'primary', STUDENT: 'neutral' }

const EMPTY_FORM = {
  id: null,
  username: '',
  password: '',
  full_name: '',
  email: '',
  role_code: 'STUDENT',
  student_code: '',
  is_active: true,
}

/** Quản lý người dùng (Admin). */
export default function Users() {
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [filters, setFilters] = useState({ role_code: '', search: '' })
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)
  const [resetting, setResetting] = useState(null)
  const [newPassword, setNewPassword] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = {}
      if (filters.role_code) params.role_code = filters.role_code
      if (filters.search.trim()) params.search = filters.search.trim()
      const [list, st] = await Promise.all([
        apiClient.get('/admin/users', { params }),
        apiClient.get('/admin/users/stats'),
      ])
      setUsers(list.data)
      setStats(st.data)
    } catch (err) {
      setError(extractErrorMessage(err, 'Không tải được danh sách người dùng.'))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setFormError('')
    setEditing('new')
  }

  const openEdit = (u) => {
    setForm({
      id: u.id,
      username: u.username,
      password: '',
      full_name: u.full_name,
      email: u.email,
      role_code: u.role.code,
      student_code: u.student_code || '',
      is_active: u.is_active,
    })
    setFormError('')
    setEditing(u.id)
  }

  const save = async () => {
    setSaving(true)
    setFormError('')
    try {
      if (editing === 'new') {
        await apiClient.post('/admin/users', {
          username: form.username,
          password: form.password,
          full_name: form.full_name,
          email: form.email,
          role_code: form.role_code,
          student_code: form.student_code || null,
        })
      } else {
        await apiClient.put(`/admin/users/${editing}`, {
          full_name: form.full_name,
          email: form.email,
          role_code: form.role_code,
          student_code: form.student_code || null,
          is_active: form.is_active,
        })
      }
      setEditing(null)
      setSuccess(editing === 'new' ? 'Đã tạo người dùng.' : 'Đã cập nhật người dùng.')
      load()
    } catch (err) {
      setFormError(extractErrorMessage(err, 'Không lưu được người dùng.'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    setError('')
    try {
      await apiClient.delete(`/admin/users/${deleting.id}`)
      setDeleting(null)
      setSuccess('Đã xoá người dùng.')
      load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không xoá được người dùng.'))
      setDeleting(null)
    }
  }

  const toggleActive = async (u) => {
    setError('')
    try {
      await apiClient.put(`/admin/users/${u.id}`, { is_active: !u.is_active })
      load()
    } catch (err) {
      setError(extractErrorMessage(err, 'Không đổi được trạng thái tài khoản.'))
    }
  }

  const resetPassword = async () => {
    setSaving(true)
    try {
      await apiClient.post(`/admin/users/${resetting.id}/reset-password`, {
        new_password: newPassword,
      })
      setResetting(null)
      setNewPassword('')
      setSuccess('Đã đặt lại mật khẩu.')
    } catch (err) {
      setError(extractErrorMessage(err, 'Không đặt lại được mật khẩu.'))
    } finally {
      setSaving(false)
    }
  }

  const statCards = stats
    ? [
        { label: 'Tổng tài khoản', value: stats.total },
        { label: 'Đang hoạt động', value: stats.active, tone: 'success' },
        { label: 'Giảng viên', value: stats.teachers, tone: 'primary' },
        { label: 'Sinh viên', value: stats.students },
      ]
    : []

  return (
    <div className="p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="font-headline-lg font-bold tracking-tight text-slate-900">
              Người dùng
            </h1>
            <p className="text-slate-600">
              Quản lý tài khoản quản trị, giảng viên và sinh viên.
            </p>
          </div>
          <button type="button" onClick={openCreate} className="btn-primary flex-shrink-0">
            <Icon name="person_add" size={18} />
            Thêm người dùng
          </button>
        </div>

        {error && <Alert variant="error">{error}</Alert>}
        {success && <Alert variant="success">{success}</Alert>}

        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {statCards.map((c) => (
              <div key={c.label} className="card p-4">
                <p className="text-sm text-slate-500">{c.label}</p>
                <p
                  className={`text-2xl font-bold mt-0.5 ${
                    c.tone === 'success'
                      ? 'text-success'
                      : c.tone === 'primary'
                        ? 'text-primary'
                        : 'text-slate-900'
                  }`}
                >
                  {c.value}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-3 items-end">
          <Input
            label="Tìm kiếm"
            value={filters.search}
            onChange={(v) => setFilters((f) => ({ ...f, search: v }))}
            placeholder="Tên hoặc tên đăng nhập…"
            className="flex-1 min-w-[240px]"
          />
          <Select
            label="Vai trò"
            value={filters.role_code}
            onChange={(v) => setFilters((f) => ({ ...f, role_code: v }))}
            options={[{ value: '', label: 'Tất cả vai trò' }, ...ROLES]}
            className="w-48"
          />
        </div>

        <Card>
          {loading ? (
            <div className="flex items-center gap-3 text-slate-500 py-8 justify-center">
              <Icon name="refresh" size={20} />
              Đang tải…
            </div>
          ) : users.length === 0 ? (
            <p className="text-center text-slate-500 py-12">Không có người dùng nào.</p>
          ) : (
            <div className="overflow-x-auto -mx-6 -mt-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-6 py-3 font-label-md">Tên đăng nhập</th>
                    <th className="px-6 py-3 font-label-md">Họ và tên</th>
                    <th className="px-6 py-3 font-label-md">Email</th>
                    <th className="px-6 py-3 font-label-md">Vai trò</th>
                    <th className="px-6 py-3 font-label-md">Mã SV</th>
                    <th className="px-6 py-3 font-label-md">Trạng thái</th>
                    <th className="px-6 py-3 font-label-md text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50">
                      <td className="px-6 py-3 font-mono text-xs text-slate-700">
                        {u.username}
                      </td>
                      <td className="px-6 py-3 text-slate-800">{u.full_name}</td>
                      <td className="px-6 py-3 text-slate-600">{u.email}</td>
                      <td className="px-6 py-3">
                        <Badge tone={ROLE_TONE[u.role.code] || 'neutral'}>
                          {u.role.name}
                        </Badge>
                      </td>
                      <td className="px-6 py-3 font-mono text-xs text-slate-500">
                        {u.student_code || '—'}
                      </td>
                      <td className="px-6 py-3">
                        <Badge tone={u.is_active ? 'success' : 'neutral'}>
                          {u.is_active ? 'Hoạt động' : 'Đã khoá'}
                        </Badge>
                      </td>
                      <td className="px-6 py-3">
                        <div className="flex justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => openEdit(u)}
                            title="Sửa"
                            className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                          >
                            <Icon name="edit" size={16} />
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setResetting(u)
                              setNewPassword('')
                            }}
                            title="Đặt lại mật khẩu"
                            className="p-2 rounded-md text-slate-500 hover:text-warning hover:bg-warning-50 transition-colors"
                          >
                            <Icon name="lock_reset" size={16} />
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleActive(u)}
                            title={u.is_active ? 'Khoá tài khoản' : 'Mở khoá'}
                            className="p-2 rounded-md text-slate-500 hover:text-primary hover:bg-primary-50 transition-colors"
                          >
                            <Icon name={u.is_active ? 'lock' : 'lock_open'} size={16} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleting(u)}
                            title="Xoá"
                            className="p-2 rounded-md text-slate-500 hover:text-error hover:bg-error-50 transition-colors"
                          >
                            <Icon name="delete" size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-sm text-slate-500 mt-4">Tổng: {users.length} tài khoản</p>
        </Card>
      </div>

      {/* Form tạo / sửa */}
      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={editing === 'new' ? 'Thêm người dùng' : `Sửa: ${form.username}`}
        footer={
          <>
            <button type="button" onClick={() => setEditing(null)} className="btn-ghost">
              Huỷ
            </button>
            <button type="button" onClick={save} disabled={saving} className="btn-primary">
              {saving ? 'Đang lưu…' : 'Lưu'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          {formError && <Alert variant="error">{formError}</Alert>}

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Tên đăng nhập"
              value={form.username}
              onChange={(v) => setForm((f) => ({ ...f, username: v }))}
              disabled={editing !== 'new'}
            />
            {editing === 'new' && (
              <Input
                label="Mật khẩu"
                type="password"
                value={form.password}
                onChange={(v) => setForm((f) => ({ ...f, password: v }))}
              />
            )}
          </div>

          <Input
            label="Họ và tên"
            value={form.full_name}
            onChange={(v) => setForm((f) => ({ ...f, full_name: v }))}
          />

          <Input
            label="Email"
            type="email"
            value={form.email}
            onChange={(v) => setForm((f) => ({ ...f, email: v }))}
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Vai trò"
              value={form.role_code}
              onChange={(v) => setForm((f) => ({ ...f, role_code: v }))}
              options={ROLES}
            />
            <Input
              label="Mã sinh viên"
              value={form.student_code}
              onChange={(v) => setForm((f) => ({ ...f, student_code: v }))}
              helper="Bỏ trống nếu không phải sinh viên."
            />
          </div>

          {editing !== 'new' && (
            <Alert variant="info">
              Tài khoản đã thi không thể xoá cứng (sẽ mất dữ liệu phục tra) — hãy dùng
              chức năng <strong>Khoá tài khoản</strong>.
            </Alert>
          )}
        </div>
      </Modal>

      {/* Đặt lại mật khẩu */}
      <Modal
        open={Boolean(resetting)}
        onClose={() => setResetting(null)}
        title="Đặt lại mật khẩu"
        footer={
          <>
            <button type="button" onClick={() => setResetting(null)} className="btn-ghost">
              Huỷ
            </button>
            <button
              type="button"
              onClick={resetPassword}
              disabled={saving || newPassword.length < 6}
              className="btn-primary"
            >
              {saving ? 'Đang đặt…' : 'Đặt lại'}
            </button>
          </>
        }
      >
        <p className="text-slate-700 mb-3">
          Đặt mật khẩu mới cho <strong>{resetting?.full_name}</strong> (
          {resetting?.username}).
        </p>
        <Input
          label="Mật khẩu mới"
          type="password"
          value={newPassword}
          onChange={setNewPassword}
          helper="Tối thiểu 6 ký tự."
        />
      </Modal>

      {/* Xác nhận xoá */}
      <Modal
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Xoá người dùng"
        footer={
          <>
            <button type="button" onClick={() => setDeleting(null)} className="btn-ghost">
              Huỷ
            </button>
            <button type="button" onClick={remove} className="btn-danger">
              Xoá
            </button>
          </>
        }
      >
        <p className="text-slate-700">
          Xoá tài khoản <strong>{deleting?.username}</strong> ({deleting?.full_name})?
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Tài khoản đã từng thi sẽ bị từ chối xoá để bảo toàn dữ liệu phục tra.
        </p>
      </Modal>
    </div>
  )
}
