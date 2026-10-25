# Đặc tả phía SEB Client: đối chiếu cấu hình & mật khẩu giám thị để thoát

> Tài liệu thiết kế, **chưa triển khai**. Bổ sung cho `docs/PLAN.md` (Phase 1) và
> `docs/SEB_GATE_DESIGN.md` (cổng bắt buộc SEB).
>
> Nguồn cảm hứng: quan sát thực tế khi dùng Safe Exam Browser của hãng — sửa mật
> khẩu SHA-256 trong file config phía client thì **vẫn vào được phòng nhưng không
> thi được**. Đó chính là hành vi đúng mà ta muốn mô phỏng: cấu hình client không
> phải nguồn sự thật, và sự lệch phải bị ghi nhận.

---

## 1. Bài học rút ra từ SEB thật

| Quan sát | Bài học áp dụng |
|---|---|
| Sửa hash trong config client → server vẫn cho vào phòng | Server không tin cấu hình do client gửi |
| Nhưng không cho thi | Có bước đối chiếu riêng, tách khỏi bước vào phòng |
| Báo lỗi chung chung, không nói lệch ở đâu | Nên nâng lên: báo rõ **trường nào lệch** để GV xử lý được |

Điểm cần cải thiện so với hành vi quan sát được: hệ thống ta nên **từ chối rõ ràng
và ghi log** thay vì "vào được nhưng không thi được" — trải nghiệm đó dễ khiến thí
sinh tưởng hệ thống lỗi.

---

## 2. Đối chiếu cấu hình client (config integrity)

### 2.1 Nguyên tắc

> **Cấu hình phía client KHÔNG bao giờ là nguồn sự thật.**
> Server công bố `config_version` + `expected_config_hash`. Client tự băm cấu
> hình của nó rồi gửi lên. Lệch → từ chối + ghi log.

Điều này có tác dụng kép:

1. Phát hiện client bị sửa file config → bằng chứng phục tra.
2. Phát hiện client quá cũ so với cấu hình mới → chặn trước khi gây lỗi kỳ lạ.

### 2.2 Cấu trúc config client

File config phía client là JSON nhỏ, chuẩn hoá (không có khoảng trắng thừa, key
sắp xếp thứ tự) để hai bên băm giống nhau:

```json
{
  "config_version": 1,
  "min_client_version": "1.0.0",
  "heartbeat_interval": 10,
  "heartbeat_timeout": 30,
  "attestation_required": true
}
```

Quy tắc băm (một bên duy nhất, dùng cho cả client và server):

```
canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
expected_config_hash = sha256(canonical.encode("utf-8")).hexdigest()
```

### 2.3 Luồng

```
1. Client đọc config file của mình, tự băm -> client_config_hash
2. POST /exam-sessions/join
     X-Client-Type: seb
     X-Client-Config-Version: 1
     X-Client-Config-Hash: <sha256>
3. Server so với seb_client_config của hệ thống
     config_version  lệch -> 409 CLIENT_CONFIG_VERSION_OUTDATED
     hash lệch       -> 422 CLIENT_CONFIG_MISMATCH  (ghi log CONFIG_MISMATCH)
4. Khớp cả hai -> tạo phiên bình thường
```

### 2.4 Server lưu gì

Trong `system_settings`, key `seb_client_config` (đã tồn tại, hiện chứa
`min_version`, `heartbeat_interval`, `heartbeat_timeout`, `attestation_required`):

```json
{
  "config_version": 1,
  "min_version": "1.0.0",
  "heartbeat_interval": 10,
  "heartbeat_timeout": 30,
  "attestation_required": true
}
```

`config_version` tăng mỗi khi GV đổi cấu hình. Khi tăng, GV phải phát hành lại
config client mới — đây là cơ chế **phát tán cấu hình có kiểm soát**.

### 2.5 Xử lý khi lệch

| Tình huống | Phản ứng |
|---|---|
| Client cũ hơn `min_version` | `409 CLIENT_VERSION_TOO_OLD`, chặn vào phòng |
| `config_version` nhỏ hơn server | `409 CLIENT_CONFIG_VERSION_OUTDATED`, báo "GV đã cập nhật cấu hình, hãy tải lại client" |
| Hash lệch nhưng version khớp | `422 CLIENT_CONFIG_MISMATCH` + ghi `CONFIG_MISMATCH` — nghi vấn cao, để GV xử lý |

**Không chỉ log rồi cho qua.** Nếu cho qua thì cơ chế này chỉ là trang trí.

---

## 3. Mật khẩu giám thị để thoát phòng thi

### 3.1 Bài toán

Thí sinh muốn dừng giữa ca (đi toilet, máy treo, hỏi bài). Nếu ai cũng thoát tự do
thì cơ chế khoá còn ý nghĩa gì. Ngược lại, chặn tuyệt đối thì sự cố kỹ thuật
làm hỏng cả ca thi.

→ Cho phép thoát, **nhưng phải có mật khẩu của giám thị**. Cổng mở theo quyết
định của GV cho từng đề.

### 3.2 Quy tắc hiệu lực

Cổng thoát **đang bật** khi thỏa cả hai:

```
policy.require_exit_password == true
AND đã thực sự đặt mật khẩu cho đề đó
```

Kiểm tra cả hai là bắt buộc. Nếu chỉ kiểm tra cờ, GV bật cờ rồi quên đặt mật
khẩu thì **thí sinh bị kẹt vĩnh viễn với không có đường thoát** — tệ hơn nhiều so
với việc cổng không bật.

### 3.3 Nơi lưu

Bảng `exam_security_configs`, **thêm một cột riêng**:

```python
exit_password_hash = Column(String(128), nullable=True)   # bcrypt
```

Không được nhét vào cột `config` (JSON) — cột này được gửi thẳng cho client trong
response của `join_exam` dưới tên `security_policy`. Đặt hash vào đó là rò rỉ bằng
chứng tới máy thí sinh.

### 3.4 Thuật toán mật khẩu — và cảnh báo quan trọng

> **Không dùng `sha256(md5(password))`.** Xem mục 5.

Dùng **bcrypt**, giống hệt phần đăng nhập (`app/core/security.py` đã có sẵn):

```python
hash_password(password)              # bcrypt.gensalt() tự sinh salt ngẫu nhiên
verify_password(plain, stored)       # bcrypt.checkpw, tự so sánh thời gian hằng số
```

Dữ liệu trong DB hiện đang ở dạng `$2b$12$...` (cost 12, 60 ký tự). Mật khẩu thoát
dùng đúng thông số đó.

### 3.5 API

| Phía | Endpoint | Nội dung |
|---|---|---|
| GV | `GET /exams/{id}/security-policy/exit-password` | `{require_exit_password, has_password, active}` — **không** trả hash |
| GV | `PUT /exams/{id}/security-policy/exit-password` | `{password}` → hash ngay, tự bật cờ |
| GV | `DELETE /exams/{id}/security-policy/exit-password` | Xoá hash, cổng tự tắt |
| Học sinh | `POST /exam-sessions/{token}/exit-unlock` | `{password}` → `{granted: true}` |

Đặt lại mật khẩu sinh hash mới (salt ngẫu nhiên). Mọi thao tác GV đều ghi
`audit_log`.

### 3.6 Chống dò mật khẩu

bcrypt cố ý chậm (~100 ms/lần). Cho phép **5 lần sai liên tiếp mỗi phiên**, sai
lần thứ 6 thì khoá phiên và ghi log.

```python
if session.exit_unlock_attempts >= 5:
    # khoá phiên, ghi log — không cho thử tiếp
```

Lưu ý trung thực: đây là biện pháp **chặn dò cơ bản**, không chống được kẻ đoán
có chủ đích. Biện pháp thật sự là **giám thị đứng cạnh phòng thi** và quy định
kỷ luật. Trong báo cáo phải nói rõ.

### 3.7 Ghi log — sự kiện KIỂM TOÁN, không tính vào ngưỡng tự nộp

| Loại | Mức | Risk score | Tính vào `total_violations`? | Khi nào |
|---|---|---|---|---|
| `EXIT_UNLOCK_GRANTED` | LOW | **0** | **KHÔNG** | Thoát hợp lệ — bằng chứng để phân biệt "nghỉ giữa ca" với "kẹt cổng" |
| `EXIT_UNLOCK_DENIED` | MEDIUM | **25** | **KHÔNG** | Sai mật khẩu — dấu hiệu cố ý lách cổng |

> ⚠ **Bẫy cần tránh (đã kiểm chứng trong code).** Auto-submit **không** kích hoạt
> bằng `risk_score`, mà bằng `total_violations >= max_allowed`. Trong
> `AnticheatService.record_violation` (dòng ~92) hiện đếm **mọi row** `ViolationLog`:
> ```
> total_violations = db.query(ViolationLog).filter(session_id==...).count()
> ```
> Nên dù `EXIT_UNLOCK_GRANTED` có `risk_score = 0`, nó **vẫn** bị cộng vào
> `total_violations` và **ăn vào ngân sách vi phạm** của thí sinh. GV dùng mật khẩu
> để cho thí sinh ra ngoài 8 lần trong một ca là phiên bị tự nộp oan.

**Cách sửa đúng** (không phải chỉ cho `risk_score = 0`):

1. Thêm cột `counts_toward_threshold` (bool, default `True`) vào bảng
   `violation_logs`, **hoặc** một tập hằng `AUDIT_ONLY_EVENT_TYPES = {
   "EXIT_UNLOCK_GRANTED", "EXIT_UNLOCK_DENIED" }` trong `anticheat_service.py`.
2. Sửa phép đếm:
   ```
   total_violations = db.query(ViolationLog)
       .filter(session_id==..., ~ViolationLog.event_type.in_(AUDIT_ONLY_EVENT_TYPES))
       .count()
   ```
   Phải lọc **ở tầng DB** (`.filter(...)`), không lọc sau khi `.count()` — nếu
   `.all()` rồi `len([...])` thì tải hết row lên RAM, không tốt.
3. `EXIT_UNLOCK_DENIED` cần một bộ đếm **riêng** (`exit_deny_count`) để GV cảnh báo
   "sai 3 lần", tách khỏi `max_violation_allowed` (ngân sách vi phạm hành vi).
4. Phải thêm cả hai vào `ALLOWED_EVENT_TYPES` và `EVENT_TYPE_SEVERITY` trong
   `app/schemas/violation_schema.py`, cùng `RISK_WEIGHTS` trong
   `app/services/anticheat_service.py` — nếu không sẽ bị validate reject.

### 3.8 Giao diện thí sinh

Nút **"Thoát & Nộp bài"** và nút logout:

- Cổng tắt → mở modal nộp bài như hiện tại.
- Cổng bật → modal **hỏi mật khẩu trước**. Sai thì báo ngay, KHÔNG đóng modal.
- Đúng → mới mở modal nộp bài.

Không bao giờ gửi `exit_password_hash` xuống client — client chỉ nhận **boolean**
`require_exit_password` trong `security_policy`.

---

## 4. Phần còn thiếu cần bổ sung

| # | Hạng mục | Nơi sửa | Trạng thái |
|---|---|---|---|
| 1 | Cột `exit_password_hash` + migration | `models/exam_security_config.py` | ☐ chưa làm |
| 2 | `require_exit_password` trong schema policy | `schemas/settings_schema.py` | ☐ chưa làm |
| 3 | `set/clear/verify/is_active` | `services/exam_security_service.py` | ☐ chưa làm |
| 4 | 3 endpoint GV + 1 endpoint học sinh | `routers/security_router.py`, `routers/exam_session_router.py` | ☐ chưa làm |
| 5 | `EXIT_UNLOCK_*` vào whitelist + risk weight | `schemas/violation_schema.py`, `services/anticheat_service.py` | ☐ chưa làm |
| 6 | **Loại `EXIT_UNLOCK_*` khỏi phép đếm `total_violations`** + bộ đếm `exit_deny_count` riêng | `services/anticheat_service.py`, `models/exam_session.py` | ☐ chưa làm — **bắt buộc**, xem cảnh báo 3.7 |
| 6 | `config_version` + `expected_config_hash` | `services/settings_service.py` | ☐ chưa làm |
| 7 | Đối chiếu config trên `join_exam` | `services/exam_session_service.py` | ☐ chưa làm |
| 8 | Cột `exit_unlock_attempts` | `models/exam_session.py` + migration | ☐ chưa làm |
| 9 | Form GV đặt mật khẩu | `frontend/.../Settings.jsx` hoặc `ExamEditor.jsx` | ☐ chưa làm |
| 10 | Modal hỏi mật khẩu khi thoát | `frontend/src/pages/exam/ExamRoom.jsx` | ☐ chưa làm |

---

## 5. Về đề xuất `sha256(md5(password))` — không nên dùng

Đề xuất này đã được ghi nhận và **không đưa vào thiết kế**. Lý do:

1. **MD5 đã lỗi thời.** Tìm được cặp va chạm MD5 trong vài giây. Đưa MD5 vào chuỗi
   băm không tạo thêm an toàn nào — nó chỉ thêm một bước yếu.

2. **Hỏng đúng thứ làm mật khẩu băm mạnh.** Mật khẩu băm bằng bcrypt/scrypt/Argon2
   cố ý **chậm** để dò mật khẩu tốn kém. `sha256(md5(pw))` chạy hàng tỷ lần/giây
   trên GPU — tức là biến một hàm băm cố ý chậm thành một hàm băm **rất nhanh**.

3. **Không có salt.** Cùng một mật khẩu cho ra cùng một hash ở mọi nơi, nên bảng
   tra cứu ngược (rainbow table) dùng được ngay. `bcrypt.gensalt()` đã xử lý
   chuyện này.

4. **Nó làm hệ thống tệ hơn `sha256` một lần.** `sha256(pw)` đã là băm nhanh không
   salt — yếu. Bọc thêm MD5 không cứu được, chỉ thêm ấn tượng "có 2 tầng".

Nếu cần một lựa chọn mạnh hơn bcrypt, hãy dùng **Argon2id** (nguyên chuẩn hiện
nay). Nhưng với hệ thống đã chạy bcrypt ở phần đăng nhập thì dùng bcrypt cho cả
hai chỗ là **nhất quán và đủ dùng** — đừng trộn hai thuật toán trong cùng hệ
thống.

Cách viết đúng trong báo cáo:

> "Mật khẩu được lưu dưới dạng hash **bcrypt** (cost 12, salt ngẫu nhiên cho mỗi
> mật khẩu). Server chỉ so khớp, không bao giờ gửi hash về client."

---

## 6. Quy trình kiểm thử

| # | Bước | Kết quả mong đợi |
|---|---|---|
| E1 | GV bật cờ nhưng chưa đặt mật khẩu | `active = false`, thí sinh thoát bình thường |
| E2 | GV đặt mật khẩu rồi `GET` | `active = true`, **không** trả hash |
| E3 | Thoát với mật khẩu sai | `401`, modal giữ nguyên |
| E4 | Thoát với mật khẩu đúng | `granted`, ghi `EXIT_UNLOCK_GRANTED`, risk score **không đổi**, `total_violations` **không đổi** |
| E5 | Sai 6 lần liên tiếp | Phiên bị khoá, ghi `EXIT_UNLOCK_DENIED`, `exit_deny_count = 6` |
| **E5b** | **GV thoát hợp lệ 8 lần, không có vi phạm nào khác** | **`total_violations` vẫn = 0, phiên KHÔNG bị tự nộp.** Test hồi quy bắt buộc — đây là lỗi đã tìm ra khi thiết kế, phải có test chặn tái phát |
| E6 | Đặt lại mật khẩu | Hash cũ không dùng được nữa |
| E7 | Xoá mật khẩu | `active = false` ngay |
| E8 | Client gửi config hash lệch | `422 CLIENT_CONFIG_MISMATCH` + ghi log |
| E9 | Client có version cũ hơn server | `409 CLIENT_CONFIG_VERSION_OUTDATED` |
| E10 | Client config khớp | Vào phòng bình thường |

Toàn bộ đều **chưa triển khai** — bảng để dành cho khi bắt tay vào code.