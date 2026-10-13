# PLAN TRIỂN KHAI — Secure Online Exam System (v3)

> Thay thế phạm vi "web-only" của SRS v2 / skills.md v2.0.
> Nguồn quyết định: GVHD cho phép làm **web trước, làm thêm Safe Exam Browser client sau**.
> Trạng thái repo hiện tại: **backend (FastAPI) gần hoàn chỉnh, `frontend/` mới chỉ có thư mục rỗng.**

---

## 0. Bối cảnh & thay đổi phạm vi

### 0.1 Phạm vi cũ (đã bị thay thế)

SRS v2 mục 9.3 và `skills.md` Quy tắc #1 ghi: *"Không triển khai ứng dụng desktop… toàn bộ hệ thống chạy trên trình duyệt Web"*, và **cấm** PySide6/PyQt/Electron/Tauri/CEF.

### 0.2 Phạm vi mới

Hệ thống gồm **2 lớp cùng tồn tại**, dùng chung một backend:

| Lớp | Tên gọi | Công nghệ | Trạng thái |
|---|---|---|---|
| **Lớp A — Web** | Exam Web Client | React + Vite + TailwindCSS | Làm trước, là phần bắt buộc nộp |
| **Lớp B — Desktop** | Safe Exam Browser Client (SEB Client) | Python + PySide6/Qt WebEngine | Làm sau, là phần nâng cao |

Ràng buộc giữ nguyên từ Quy tắc #2: **mọi business logic, chấm điểm, cấu hình đề và đáp án đều nằm ở backend FastAPI**. SEB Client chỉ là một lớp vỏ bất biết gì về nghiệp vụ — đây cũng chính là nền tảng của chiến lược chống crack ở Phase 2.

### 0.3 Cơ chế cốt lõi: cờ `require_safe_browser`

Đây là tính năng trung tâm của toàn bộ plan, và là câu trả lời cho yêu cầu *"web có toggle được only through safe exam browser"*.

```
Quyết định cuối cùng = (exam.require_safe_browser == true)
                       AND (system_settings.require_safe_browser_global == true)

  → Client BẮT BUỘC phải là SEB Client đã XÁC THỰC được (challenge-response HMAC)
  → Nếu thí sinh dùng web: phiên vẫn tạo ở restricted_mode = true
    + ghi log UNAUTHORIZED_CLIENT làm bằng chứng phục tra
    + frontend hiển thị PolicyGate hướng dẫn dùng SEB Client (xem mục 3.4)
    + nếu GV tắt allow_web_fallback -> thí sinh phải chuyển sang SEB Client

Quyết định = false
  → Cả Web lẫn SEB Client đều thi được, mức ràng buộc khác nhau (xem mục 3.5)
```

> **Ghi chú quan trọng (Quy tắc #5):** đây là cơ chế **RĂN ĐE + GHI NHẬN BẰNG CHỨNG**, không phải ngăn chặn tuyệt đối. Cờ này không làm gì nếu thí sinh không chịu dùng SEB Client; nó chỉ đảm bảo rằng ai dùng web đều **để lại dấu vết phục tra**. Giá trị thật của nó nằm ở chỗ hệ thống *phân biệt được* phiên thi hợp lệ với phiên thi không qua kiểm chứng.

Hệ quả: GV có thể **tắt** yêu cầu bắt buộc cho từng đề ngay cả khi toàn trường đang bật — tránh tình huống một đề bất thường chặn cả lớp.

---

## PHASE 0 — Nền tảng chung (Web + toggle + config)

> Phase này **không cần** tới SEB Client. Làm xong Phase 0 thì đã có hệ thống web chạy được và demo được.
> Phase 0 cũng tạo sẵn mọi "chỗ móc" (hook, schema, endpoint) để Phase 1–2 cắm vào mà không phải sửa lại.

### 0.1 Mục tiêu

1. Toggle `require_safe_browser` ở **cấp hệ thống** (Admin) và **cấp đề** (Teacher).
2. Bộ **config khoá an toàn** có cấu trúc, lưu DB, đẩy xuống client, và server **tự kiểm tra lại** khi nhận vi phạm.
3. Giao diện làm bài trên web với đầy đủ cơ chế khoá tầng trình duyệt.
4. Nền tảng xác thực client (nonce + HMAC) — web thi mà không có, SEB Client thi mà phải có.

### 0.2 Thay đổi CSDL

> Theo Quy tắc #7: bảng số nhiều snake_case, có `created_at`/`updated_at`, FK `<tên bảng số ít>_id`.
> Migration Alembic tên `<timestamp>_<mô tả>.py`.

**Migration 1 — `<ts>_add_require_safe_browser_and_settings.py`**

```sql
-- exams: thêm cột toggle cấp đề
ALTER TABLE exams ADD COLUMN require_safe_browser TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE exams ADD COLUMN updated_at DATETIME NULL;

-- bảng cấu hình toàn cục (key-value, giá trị JSON)
CREATE TABLE system_settings (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    setting_key   VARCHAR(100) NOT NULL UNIQUE,
    setting_value JSON NOT NULL,
    updated_by    INT NULL,          -- FK users.id ON DELETE SET NULL
    updated_at    DATETIME NOT NULL,
    INDEX idx_settings_key (setting_key)
);

-- seed
INSERT INTO system_settings (setting_key, setting_value) VALUES
('require_safe_browser_global', 'false'),
('seb_client_config',          '{"min_version":"1.0.0","heartbeat_interval":10,"attestation_required":false}');
```

**Migration 2 — `<ts>_add_exam_security_config.py`**

```sql
-- config khoá an toàn chi tiết, 1 đề = 1 bản ghi (JSON)
CREATE TABLE exam_security_configs (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    exam_id      INT NOT NULL,        -- FK exams.id ON DELETE CASCADE, UNIQUE
    config       JSON NOT NULL,
    updated_at   DATETIME NOT NULL,
    UNIQUE KEY uq_exam_config (exam_id)
);
```

> **Vì sao tách bảng riêng thay vì nhét cột JSON vào `exams`?** Vì `exams` đang được đọc bởi list endpoint dày đặc; config JSON chỉ cần ở endpoint lấy đề. Tách ra giữ `ExamResponse` gọn và tránh kéo theo lỗi N+1 ở danh sách đề.

**Cấu trúc `exam_security_configs.config` (schema chuẩn, Pydantic `ExamSecurityConfig`):**

| Field | Kiểu | Mặc định | Ý nghĩa |
|---|---|---|---|
| `require_fullscreen` | bool | true | Bắt fullscreen khi vào phòng |
| `block_copy_paste` | bool | true | Chặn Ctrl+C/V/X, chuột phải |
| `block_devtools` | bool | true | Chặn F12, Ctrl+Shift+I/J/C |
| `detect_devtools` | bool | true | Heuristic phát hiện DevTools đang mở |
| `monitor_tab_switch` | bool | true | `visibilitychange` + `blur` |
| `lock_navigation` | bool | true | Chặn rời khỏi domain thi, chặn back/forward |
| `max_tab_switch` | int | 5 | Ngưỡng → auto-submit (server kiểm lại) |
| `max_fullscreen_exit` | int | 3 | Ngưỡng thoát fullscreen |
| `auto_submit_on_threshold` | bool | true | Có tự nộp bài khi vượt ngưỡng |
| `warn_countdown_seconds` | int | 10 | Mức 2: đếm ngược yêu cầu quay lại |
| `disable_print` | bool | true | Chặn Ctrl+P |

**Ghi đè `exams.max_violation_allowed`:** field cũ này vẫn giữ nguyên để không phá dữ liệu, nhưng `ExamSecurityConfig.max_tab_switch + max_fullscreen_exit` là nguồn chuẩn. Trong `anticheat_service`, ngưỡng lấy theo thứ tự: `exam_security_configs` → fallback `exams.max_violation_allowed`.

### 0.3 Thay đổi Backend

| File | Thay đổi |
|---|---|
| `models/system_setting.py` | **Mới.** ORM cho bảng `system_settings`. |
| `models/exam_security_config.py` | **Mới.** ORM cho bảng `exam_security_configs`. |
| `models/exam.py` | Thêm `require_safe_browser`, `updated_at`, relationship `security_config`. |
| `schemas/settings_schema.py` | **Mới.** `SystemSettingPublic/Update`, `SebClientConfig`. |
| `schemas/exam_schema.py` | Thêm `SecurityConfig` vào `ExamDetailResponse`, `require_safe_browser` vào create/update. |
| `schemas/client_attestation_schema.py` | **Mới.** `AttestationChallenge`, `AttestationResponse`, `ClientIdentity`. |
| `services/settings_service.py` | **Mới.** Đọc/ghi cấu hình toàn cục, có cache trong bộ nhớ + TTL. |
| `services/exam_security_service.py` | **Mới.** `get_effective_policy(exam_id)` — hợp nhất cờ toàn cục + config đề + default. Đây là **nguồn sự thật duy nhất**, cả Web lẫn SEB Client đều đọc chính endpoint này. |
| `services/attestation_service.py` | **Mới.** Sinh nonce, xác minh HMAC, phát `client_attestation_key`. |
| `dependencies/client_identity.py` | **Mới.** Dependency `verify_client_identity` đọc header, trả `ClientIdentity`. |
| `api/routers/settings_router.py` | **Mới.** `GET/PUT /api/admin/settings/...` (role ADMIN). |
| `api/routers/security_router.py` | **Mới.** `GET /api/exams/{id}/security-policy` (role STUDENT, chỉ trong ca thi — trả cấu hình đã resolve, không có bí mật). |
| `api/routers/exam_router.py` | Nối create/update đề với `require_safe_browser` + upsert config. |
| `api/routers/exam_session_router.py` | `join_exam` nhận `ClientIdentity`, áp dụng chính sách (mục 3.4). |
| `services/anticheat_service.py` | Nạp ngưỡng từ `exam_security_service` thay vì đọc thẳng `exam.max_violation_allowed`. |
| `services/grading_service.py` | Không đổi logic, chỉ bổ sung cột `attestation_status` vào kết quả trả về. |

**Luồng xác thực client (nonce + HMAC) — chi tiết (ĐÃ TRIỂN KHAI, xem `backend/app/services/attestation_service.py`):**

```
1. Client đăng nhập bằng tài khoản thí sinh → nhận access_token (JWT) như hiện tại.
2. Client POST /api/auth/client-nonce   (bắt buộc có Bearer token)
   ← Server:
        a) cấp `device_secret_salt` cho user nếu chưa có (random 16 bytes, lưu dạng hex)
        b) sinh nonce ngẫu nhiên 32 bytes (token_urlsafe), lưu vào store in-memory
           kèm user_id + hạn 30 giây
   ← { "nonce": "<base64 32 bytes>", "expires_in": 30 }

3. Client dẫn xuất khoá và ký:
        device_secret = HMAC-SHA256(key = SECRET_KEY, msg = "device_secret|<user_id>|<salt>")
        message       = "nonce|client_version|device_fingerprint"
        signature     = base64( HMAC-SHA256(key = device_secret, msg = message) )

4. Client POST /api/auth/client-attest
      Body: { nonce, client_version, device_fingerprint, signature }
   ← Server:
        a) tra nonce trong store; KHÔNG có -> trả attested=false (ghi log NONCE_INVALID_OR_EXPIRED)
        b) XOÁ nonce ngay lập tức -> chặn replay
        c) kiểm tra hạn 30s và nonce có thuộc đúng user đang xác thực
        d) dẫn xuất lại `device_secret` từ salt + SECRET_KEY, so sánh chữ ký
           bằng `hmac.compare_digest` (so sánh thời gian hằng số)
        e) hợp lệ -> sinh `attestation_key` (dùng ký heartbeat ở Phase 1),
           lưu `key_salt` vào `client_attestations` để xác minh về sau
   ← { "attested": true, "attestation_key": "<base64>", "client_version": "...", ... }
```

> **Khoá `device_secret` KHÔNG bao giờ được lưu trong DB** — chỉ lưu `device_secret_salt`. Kể cả bị dump toàn bộ CSDL mà không có `SECRET_KEY` trong `.env` thì không dựng lại được chữ ký hợp lệ. Đây là điểm mấu chốt chống giả mạo header bằng curl.
>
> **Giới hạn phải nói thẳng (Quy tắc #5):** đây là chống giả mạo ở mức đồ án, **không phải DRM thương mại**. Kẻ tấn công có source client vẫn chạy client thật một lần để lấy `device_secret`. Biện pháp mạnh hơn là **code signing** — xem mục 2.2, hàng C6.
>
> **Hạn chế kiến trúc:** store nonce hiện là **in-memory**, phục vụ môi trường chạy 1 tiến trình. Khi chạy multi-worker (uvicorn `--workers >1`) phải đổi sang Redis/DB để các worker chia sẻ nonce — nếu không, client có thể xin nonce ở worker A rồi verify ở worker B và luôn thất bại.
>
> **Web client KHÔNG gọi bước 3–4** (nó không có khoá để ký). Header `X-Client-Type` của web chỉ được server dùng để chọn nhánh xử lý, **không phải bằng chứng**. Thí sinh tự khai `X-Client-Type: seb` mà không attest được thì vẫn bị tính là `restricted_mode`.

### 0.4 Thay đổi Frontend — **ĐÃ TRIỂN KHAI**

```
frontend/src/
├── pages/
│   ├── auth/            Login.jsx ✅
│   ├── admin/
│   │   ├── AdminHome.jsx          ✅
│   │   └── Settings.jsx           ★ Toggle "Chỉ cho phép Safe Exam Browser" + config SEB Client + config khoá mặc định ✅
│   ├── teacher/
│   │   ├── TeacherHome.jsx        ✅
│   │   ├── ExamList.jsx           ✅ (khung, chờ nối API danh sách)
│   │   └── ExamEditor.jsx         ★ Toggle cấp đề + form cấu hình khoá ✅
│   ├── exam/            ★ Lớp A — giao diện làm bài (web)
│   │   ├── ExamJoin.jsx           ✅ Nhập mã phòng
│   │   ├── ExamRoom.jsx           ★ Phòng thi: navigator câu hỏi + đồng hồ + dải cơ chế bảo vệ ✅
│   │   ├── ExamResults.jsx        ✅
│   │   ├── PolicyGate.jsx         ★ Màn hình cảnh báo khi đề bắt buộc SEB mà đang dùng web ✅
│   │   └── hooks/
│   │       ├── useSecurityPolicy.js     ★ NGUỒN GỐC: nạp policy + logViolation + heartbeat ✅
│   │       ├── useFullscreenLock.js     ✅
│   │       ├── useVisibilityMonitor.js  ✅
│   │       ├── useKeyboardBlock.js      ✅
│   │       ├── useDevToolsDetector.js   ✅
│   │       ├── useNavigationLock.js     ★ chặn rời domain, back/forward ✅
│   │       └── useAutoSave.js           ✅
├── components/
│   ├── common/          Icon.jsx, Card.jsx, Input.jsx, Select.jsx, Toggle.jsx ★, Modal.jsx, Badge.jsx, Alert.jsx ✅
│   └── layout/          Layout.jsx (sidebar 260px), ProtectedRoute.jsx ✅
├── services/            apiClient.js, socketClient.js, policyService.js ★ ✅
├── store/               authStore.js (Zustand) ✅
├── App.jsx              Định tuyến theo vai trò ✅
├── index.css            Token dùng chung (.btn-*, .card, .input, .chip, .qnum) ✅
└── tailwind.config.js   Token màu/typography lấy từ màn hình Stitch ✅
```

**Nguyên tắc đã áp dụng (Quy tắc #3 & #6):** mỗi cơ chế 1 hook riêng, UI **không** tự viết logic khoá. `useSecurityPolicy` là hook gốc — 6 hook khoá còn lại đọc policy từ đây, **không hardcode** `true`/`false`. Tắt cờ trong DB là thực sự tắt, không phải chỉ tắt nhãn.

**Luồng thực tế trong `ExamRoom.jsx`:**
```
join_exam → response có security_policy + require_safe_browser + restricted_mode
  → useSecurityPolicy() cấp policy cho mọi hook con
  → nếu require_safe_browser && restricted_mode → hiện PolicyGate
  → (nếu GV bật allow_web_fallback) thí sinh chọn "Thi chế độ hạn chế" → vào phòng
  → mỗi cơ chế kích hoạt -> logViolation() gửi Socket.IO -> server tự quyết định mức xử lý
  → server phát force_submit -> hook gọi submitExam('AUTO_VIOLATION')
```

**Màn hình `PolicyGate.jsx` (đã build):**
- Icon cảnh báo, tiêu đề lỗi, mã phòng thi.
- Hướng dẫn 3 bước: tải SEB Client → mở → nhập mã phòng.
- 3 nút tải client theo hệ điều hành (Windows / macOS / Linux) — hiện là placeholder, sẽ nối URL thật ở Phase 1.
- Nút "Tôi đã cài SEB Client — Thử lại" và "Thi bằng trình duyệt với chế độ hạn chế" (chỉ hiện nếu GV bật `allow_web_fallback`).

**Về Design System:** theo quyết định của người dùng ở v3.1, giao diện **không bắt buộc** tuân thủ `design.md`; token thực tế lấy từ các màn hình Stitch và nằm trong `frontend/tailwind.config.js`. Xem `skills.md` Quy tắc #8 v3.1.

### 0.5 Tiêu chí hoàn thành Phase 0

- [x] Viết migration thật cho `initial_schema` + migration Phase 0; `alembic upgrade head` và `downgrade base` chạy sạch (đã kiểm tra trên SQLite).
- [x] Toggle `require_safe_browser_global` đọc/ghi qua `settings_service`, có fallback khi DB chưa seed.
- [x] Quy tắc hiệu lực `(cờ đề) AND (cờ hệ thống)` — GV tắt được cho từng đề.
- [x] `ExamSecurityService.resolve_policy()` là nguồn sự thật duy nhất, dùng chung cho web lẫn SEB Client.
- [x] Challenge-response HMAC: nonce 1 lần, chữ ký gắn `nonce|version|fingerprint`, khoá không lưu rõ trong DB.
- [x] `pytest tests/` → **75 passed** (gồm `test_heartbeat_monitor` và `test_import_service`) (gồm `test_phase0_security`, `test_exam_session_fixes`, `test_heartbeat_monitor`).
- [x] Backend: router quản lý người dùng + nhật ký audit (`admin_router.py`), `AuditService` ghi vào `audit_logs` (trước đó bảng này luôn rỗng).
- [x] Backend: vòng quét heartbeat nền (`heartbeat_monitor.py`) — phát hiện mất kết nối, đánh dấu `DISCONNECTED`, ghi log `CONNECTION_LOST`.
- [x] Backend: phát hiện `DUPLICATE_LOGIN` — cùng phiên mở 2 socket thì kick kết nối cũ và ghi log.
- [x] Frontend: Mức 2 — cảnh báo đếm ngược dùng `warn_countdown_seconds` (trước đó cấu hình này không được dùng ở đâu).
- [x] Tài liệu: `docs/BAOCAO_LIMITATION.md` (bắt buộc theo Quy tắc #5) và `README.md`.
- [x] Frontend React: `PolicyGate.jsx`, `useSecurityPolicy.js`, form toggle trong `Settings.jsx` / `ExamEditor.jsx` — **đã build, `npm run build` + ESLint sạch**.
- [x] 7 hook khoá an toàn tách bạch, mỗi cơ chế 1 file.
- [x] Icon đi qua `components/common/Icon.jsx`; màu/spacing lấy từ token `tailwind.config.js`.
- [ ] Mở `http://localhost:5173` kiểm thử thực tế với backend đang chạy (toggle bật/tắt, vào phòng thi).
- [ ] Module còn lại (Ngân hàng câu hỏi, Lịch thi, Báo cáo, Dashboard giám sát) — hiện là khung trang, chờ nối API ở các phase sau.

### 0.6 Các bản vá bảo mật đã áp dụng khi triển khai Phase 0

Ngoài tính năng mới, quá trình rà soát backend phát hiện và đã sửa các lỗi sau — **đây là những lỗi có trong code trước Phase 0**:

| # | Vấn đề | Mức | Đã sửa tại |
|---|---|---|---|
| 1 | `initial_schema` migration rỗng (`pass`) — Alembic không quản lý được CSDL, toàn bộ bảng do `seed_data.py` tạo bằng `create_all`. Mất khả năng rollback/upgrade. | Nghiêm trọng | `alembic/versions/20260921_2145_initial_schema.py` (viết đầy đủ 11 bảng) |
| 2 | `save_answer` **không chặn deadline phía server** — gọi API trực tiếp sau khi hết giờ vẫn lưu được đáp án, dù đồng hồ trên UI đã về 0. | **Nghiêm trọng** | `exam_session_service.py` — thêm `_get_deadline()` theo đồng hồ server (Quy tắc #4.1) |
| 3 | `save_answer` **không kiểm tra câu hỏi có thuộc đề** — thí sinh gửi `question_id` bất kỳ để dựng bài giả trong kỳ thi. | **Nghiêm trọng** | `exam_session_service.py` — kiểm tra qua `exam_questions` |
| 4 | `save_answer` **không kiểm tra lựa chọn có thuộc câu hỏi** — có thể chọn option của câu khác. | Cao | `exam_session_service.py` |
| 5 | `event_type` và `severity` của vi phạm **do client tự khai**, không whitelist — làm sai lệch thống kê và risk score. | Cao | `violation_schema.py` (`ALLOWED_EVENT_TYPES` + `resolve_severity()`), `exam_namespace.py` |
| 6 | `submit_type` **nhận chuỗi bất kỳ** từ client, ghi thẳng vào DB. | Trung bình | `exam_session_service.py` (`ALLOWED_SUBMIT_TYPES`) |
| 7 | CORS `allow_origins=["*"]` **cùng** `allow_credentials=True` — tổ hợp bất hợp lệ theo đặc tả CORS, browser từ chối preflight khi gửi `Authorization`. | Trung bình | `main.py` — dùng `settings.CORS_ORIGINS` |
| 8 | Đối chiếu thời gian dùng `.replace(tzinfo=utc)` cho datetime **naive** — sai múi giờ nếu DB lưu giờ địa phương. | Trung bình | `security.py` — thêm `to_utc_naive()` dùng thống nhất |
| 9 | `exam_namespace.violation` đọc `session.schedule.exam.max_violation_allowed` — không nạp `schedule` nên dễ `DetachedInstanceError`, và bỏ qua config theo đề. | Trung bình | `exam_namespace.py` — `joinedload` + `AnticheatService.resolve_max_violations()` |
| 10 | `session_token` khai báo là query param trong route POST nhưng client gửi trong body → **mọi lần tự lưu và nộp bài trả 422**. | **Nghiêm trọng** | Chuyển `session_token` vào `SaveAnswerRequest` / `SubmitExamRequest` |
| 11 | `attested` hardcode `False` trong `get_client_identity` → SEB Client thật cũng không vượt qua được cờ `require_safe_browser`. | **Nghiêm trọng** | Thêm token xác thực ngắn hạn (JWT 5 phút) do `AttestationService` cấp, ràng buộc user + fingerprint |
| 12 | `HEARTBEAT_TIMEOUT_SECONDS` có trong config nhưng **không nơi nào dùng** → cắm máy giữa kỳ thi không bị ghi nhận. | Cao | `services/heartbeat_monitor.py` — vòng quét nền 10s |
| 13 | `DUPLICATE_LOGIN` có trong whitelist nhưng **không nơi nào phát ra**. | Cao | `exam_namespace.join_exam_room` — kick socket cũ, ghi log |
| 14 | Bảng `audit_logs` có trong CSDL từ migration đầu nhưng **không có nơi nào ghi** → cột dữ liệu luôn rỗng. | Cao | `services/audit_service.py` + `api/routers/admin_router.py` |
| 15 | `warn_countdown_seconds` cấu hình được nhưng **frontend không dùng** → mức 2 (cảnh báo) không tồn tại. | Cao | `hooks/useViolationWarning.js` + overlay đếm ngược |
| 16 | `seed_data.py` tạo ca thi với mốc thời gian tương lai → chạy lại seed vài ngày sau là ca hết hạn, không demo được. | Thấp | Tự lùi khung giờ về hiện tại nếu đã hết hạn |

### 6.7 Nhập câu hỏi hàng loạt từ .docx (bổ sung ngoài kế hoạch ban đầu)

Nhập từng câu bằng tay tốn thời gian và dễ sai, nên bổ sung luồng nhập hàng loạt.

| Thành phần | Nội dung |
|---|---|
| `services/import_service.py` | Parser thuần: đọc bảng Word, văn bản phân tách, chuẩn hoá đáp án, suy ra loại câu hỏi |
| `services/question_import_service.py` | Quản lý vòng đời: đọc thử → token → ghi hàng loạt; sinh file .docx mẫu |
| `POST /questions/import/preview` | Đọc thử, **không ghi CSDL**. Trả số câu hợp lệ / trùng / lỗi kèm số dòng |
| `POST /questions/import/commit` | Ghi vào ngân hàng trong **1 transaction** |
| `GET /questions/import/template` | Tải file .docx mẫu có định dạng chuẩn |

**Quyết định thiết kế quan trọng:**

- **Luôn qua 2 bước.** Import thẳng là rủi ro: GV tải nhầm file, bấm Import, xong mới thấy hàng chục câu sai định dạng — dữ liệu đã bẩn thì sửa cũng mệt.
- **Khoá đọc thử lưu trong bộ nhớ với TTL 30 phút.** Client gửi lại danh sách đã sửa thì không thể tiêm dữ liệu lạ; hết hạn thì phải đọc thử lại.
- **Đáp án linh hoạt.** `C` · `A,C` · `AC` · `1,3` · `a) c)` — vì GV thói quen viết khác nhau.
- **Tự suy ra loại câu hỏi** từ số đáp án đúng, không bắt GV khai thêm.
- **Lỗi cục bộ, không chặn cả file.** Câu hỏi hỏng bị bỏ qua kèm số dòng để GV tự sửa.
- **Chống trùng bằng fingerprint** (chuẩn hoá khoảng trắng/hoa thường/dấu câu, băm SHA-256). Kiểm tra lại lúc ghi vì có thể đã có câu mới thêm giữa lúc đọc thử và lúc commit.

> **Bài học cho các Phase sau:** luôn nạp quan hệ cần thiết bằng `joinedload` **trước** khi `commit()`; sau commit, các đối tượng bị `expire` và truy cập thuộc tính quan hệ sẽ ném lỗi detached.

---

## PHASE 1 — Safe Exam Browser Client (PySide6 / Qt WebEngine)

> Phase này xây **lớp B**. Lớp A (web) vẫn chạy song song và không bị ảnh hưởng.

### 1.1 Vì sao chọn PySide6/Qt WebEngine

| Tiêu chí | PySide6 + WebEngine | CEF/PyQt | Electron | Trình duyệt web thuần |
|---|---|---|---|---|
| Viết bằng Python | ✅ | ✅ | ❌ (Node) | ✅ |
| Đóng gói đa nền tảng từ 1 codebase | ✅ | ✅ | ⚠️ | ⚠️ |
| Khoá fullscreen/kiosk thật | ✅ mạnh | ✅ mạnh | ⚠️ | ❌ |
| Chặn DevTools | ✅ cấu hình được | ✅ | ⚠️ | ❌ |
| Khoá clipboard ở tầng ứng dụng | ✅ | ✅ | ⚠️ | ❌ |
| Chặn phím ở tầng Qt (trước khi tới web) | ✅ | ✅ | ⚠️ | ❌ |
| Miễn phí / mã nguồn mở | ✅ | ⚠️ PyQt v5+ GPL/commercial | ⚠️ | ✅ |

Đã xác nhận hướng này theo yêu cầu. Giờ dùng nó.

### 1.2 Cấu trúc thư mục

```
seb_client/                        # ★ Thư mục mới, cấp cao hơn backend/ và frontend/
├── main.py                        # Entry point
├── requirements.txt
├── sebclient/
│   ├── app.py                     # Khởi tạo QApplication, QWebEngineView
│   ├── config.py                  # Đọc .env / file cấu hình cục bộ
│   ├── constants.py
│   ├── api/
│   │   ├── client.py              # HTTP client gọi backend FastAPI
│   │   ├── attestation.py         ★ Xác thực HMAC (nonce → attestation_key)
│   │   └── heartbeat.py           ★ Socket.IO client, ký HMAC mỗi nhịp
│   ├── guards/                    # ★ Mỗi cơ chế 1 module
│   │   ├── base.py                # BaseGuard: enable/disable, log violation
│   │   ├── kiosk_guard.py         # Fullscreen, ẩn thanh taskbar/dock
│   │   ├── keyboard_guard.py      # Chặn F12/Ctrl+Shift+I, Ctrl+C/V/X/P/U
│   │   ├── clipboard_guard.py     # Khoá clipboard hệ thống khi thi
│   │   ├── navigation_guard.py    # Chặn URL ngoài domain thi, chặn window.open
│   │   ├── devtools_guard.py      # Tắt DevTools qua Qt API
│   │   ├── download_guard.py      # Chặn tải file, chặn in
│   │   └── session_guard.py       # Theo dõi vòng đời phiên thi
│   ├── osint/                     # ★ TÁC ĐỘNG HỆ ĐIỀU HÀNH — đa nền tảng
│   │   ├── platform.py            #   Dispatcher: phát hiện OS → trả module con
│   │   ├── base.py                #   BaseOSAdapter — interface chung
│   │   ├── windows_adapter.py     #   ↳ pywin32 / ctypes
│   │   ├── macos_adapter.py       #   ↳ AppKit qua PyObjC, Quartz
│   │   ├── linux_adapter.py       #   ↳ Xlib/Wayland portal
│   │   └── capability_matrix.py   #   Bảng: tính năng nào có trên OS nào
│   ├── integrity/                 # ★ Chống crack — xem Phase 2
│   │   ├── self_check.py
│   │   ├── anti_debug.py
│   │   └── license_check.py
│   └── ui/
│       ├── login_window.py        # Đăng nhập + nhập mã phòng
│       ├── exam_window.py         # Cửa sổ thi
│       ├── warning_overlay.py     # Đếm ngược mức 2
│       └── blocked_overlay.py     # Màn hình PolicyGate (bản desktop)
├── packaging/
│   ├── build_windows.ps1
│   ├── build_macos.sh
│   ├── build_linux.sh
│   └── version_info.py
└── tests/
    └── test_guards.py
```

> Theo Quy tắc #6, đây là **một sản phẩm độc lập** nên có thư mục riêng ở cấp gốc — không nhét vào `backend/app/`.

### 1.3 Tác động hệ điều hành — thiết kế lớp trừu tượng đa OS

Đây là phần bạn nói chưa biết làm. Nguyên tắc chỉ đạo: **mọi khác biệt OS nằm sau interface, phần logic không bao giờ rẽ nhánh `if windows / if mac / if linux`.**

```python
# seb_client/sebclient/osint/base.py
from abc import ABC, abstractmethod

class BaseOSAdapter(ABC):
    """Interface chung cho mọi nền tảng. Logic guards chỉ nói chuyện với interface này."""

    os_name: str          # "windows" | "macos" | "linux"
    supports: set[str]    # tập capability mà OS này có

    @abstractmethod
    def enter_kiosk(self) -> None: ...
    @abstractmethod
    def exit_kiosk(self) -> None: ...

    @abstractmethod
    def is_screen_locked(self) -> bool:
        """Windows bị khoá màn hình (UAC secure desktop) — chặn được thật."""

    @abstractmethod
    def detect_monitor_switch(self) -> str | None:
        """Trả tên cửa sổ đang chiếm foreground NGAY TRONG GIÂY CƯỚC.
        Đây là phần mạnh nhất mà web KHÔNG làm được."""

    @abstractmethod
    def lock_clipboard(self) -> None: ...
    @abstractmethod
    def unlock_clipboard(self) -> None: ...

    @abstractmethod
    def detect_vm_or_sandbox(self) -> tuple[bool, list[str]]:
        """Trả (có phải VM không, danh sách dấu hiệu)."""

    @abstractmethod
    def block_screen_capture(self) -> bool:
        """Windows 10 1803+: SetDisplayAffinity(DISPLAY_AFFINITY_READONLY).
        macOS: không có API tương đương cho app thường.
        Linux: Wayland chặn, X11 có thể cấu hình.
        → Trả False nếu OS không hỗ trợ, guards phải biết để BÁO CÁO
          'không áp dụng được' thay vì im lặng giả vờ chống được."""

    @abstractmethod
    def detect_debugger(self) -> bool: ...

    @abstractmethod
    def process_watch_loop(self, forbidden: set[str], on_detect) -> None:
        """Giám sát tiến trình: task manager, remote desktop, phần mềm chụp màn hình..."""

    @abstractmethod
    def device_fingerprint(self) -> str: ...
```

#### Ma trận năng lực theo OS (đưa thẳng vào báo cáo)

| Cơ chế | Windows | macOS | Linux (X11) | Linux (Wayland) |
|---|---|---|---|---|
| Kiosk fullscreen thật | ✅ `SetDisplayAffinity` + ẩn taskbar | ✅ ẩn Dock, `NSWindow` fullscreen | ✅ cửa sổ undecorated | ⚠️ giới hạn |
| Phát hiện Alt+Tab (ngay lập tức) | ✅ `GetForegroundWindow` | ✅ `NSWorkspace` | ✅ `_NET_ACTIVE_WINDOW` | ❌ không có |
| Khoá clipboard hệ thống | ✅ `OpenClipboard` chain | ✅ `NSPasteboard` | ✅ `QLocalClipboard` | ⚠️ |
| Chặn chụp màn hình | ✅ `DISPLAY_AFFINITY_READONLY` | ⚠️ `CGWindowListCreateImage` cần entitlement | ⚠️ | ✅ portal |
| Chặn task manager | ⚠️ phát hiện được | ✅ | ✅ | ✅ |
| Phát hiện VM/sandbox | ✅ | ✅ | ✅ | ✅ |
| Phát hiện debugger | ✅ `IsDebuggerPresent` | ✅ `sysctl P_TRACED` | ✅ `/proc/self/status` | ✅ |

> **Cột "⚠️/❌" là những ô trống thật, phải nêu trong báo cáo theo Quy tắc #5.** Client **không được** im lặng bỏ qua — phải gửi lên server `violation` với `detail.unsupported = ["wayland_monitor_switch"]` để GV biết máy đó không được hỗ trợ đầy đủ.

#### Phát hiện chuyển cửa sổ — cơ chế cốt lõi mà web không có

```python
# seb_client/sebclient/osint/windows_adapter.py
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

def detect_monitor_switch(self) -> str | None:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    if hwnd == self._main_hwnd:      # vẫn là cửa sổ thi → OK
        return None
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    title = buf.value.strip()
    if not title:
        return "<ẩn danh>"
    return title
```

Vòng lặp gọi hàm này mỗi **300 ms**. Phát hiện tên cửa sổ lạ → `TAB_SWITCH` hoặc type mới `FOREIGN_WINDOW_DETECTED` (xem mục 4.1).

> **Khác biệt then chốt so với web:** web chỉ biết "tab đã ẩn", biết *sau khi* người dùng đã Alt+Tab. Client biết **cửa sổ nào** đang chiếm foreground. Đây là lý do cấp B đáng giá.

### 1.4 Luồng nghiệp vụ của SEB Client

```
Mở app
  → LoginWindow: đăng nhập (tài khoản thí sinh) → nhập mã phòng
  → GET /client-nonce  →  HMAC  →  POST /client-attest
  → Server trả { attested: true, attestation_key, policy, exam_url }
  → ExamWindow: QWebEngineView nạp exam_url
  → Bật các guard theo `policy` (từng guard tự bật/tắt theo cờ trong policy)
  → Vòng lặp: heartbeat 10s (có ký HMAC) + monitor OS 300ms
  → Vi phạm → emit lên server → policy quyết định cảnh báo / đếm ngược / khoá
  → Hết giờ hoặc vượt ngưỡng → server trả lệnh khoá → client khoá & đóng
```

**Điểm quan trọng:** client **không tự quyết định** nộp bài. Nó chỉ nhận lệnh. Đây là Quy tắc #4 áp dụng cho cả 2 lớp.

### 1.5 Tiêu chí hoàn thành Phase 1

- [ ] Chạy được trên cả 3 OS từ cùng codebase, chỉ khác lệnh build.
- [ ] `python -m seb_client` mở được login → vào phòng thi → làm bài → nộp.
- [ ] Alt+Tab sang cửa sổ khác → phát hiện trong ≤ 300 ms, có tên cửa sổ trong log.
- [ ] F12 / Ctrl+Shift+I / Ctrl+C / Ctrl+V / chuột phải → không có tác dụng.
- [ ] Click link ngoài domain thi hoặc `window.open` → bị chặn, ghi log.
- [ ] Trên Wayland: client **báo cáo** thiếu hỗ trợ monitor switch, không im lặng.
- [ ] `pytest seb_client/tests/` — guard nào bật/tắt đúng theo policy.

---

## PHASE 2 — Chống crack & bảo vệ client

> Mục tiêu thật: **không phải "bất khả xâm phạm"** (điều đó không tồn tại với phần mềm chạy trên máy của người dùng), mà là **làm cho việc gian lận tốn kém hơn rất nhiều so với làm thẳng, và luôn để lại bằng chứng phục tra**.

### 2.1 Nguyên tắc chiến lược: Server là nguồn sự thật

Đây là biện pháp chống crack **mạnh nhất và rẻ nhất**, và nó đã được xây xong ở Phase 0:

1. **Đáp án đúng không bao giờ tới client.** `QuestionPublic` không có `is_correct`. Client crack được cũng không biết đáp án.
2. **Config đề không nằm trong binary.** Client tải policy từ server mỗi lần vào phòng.
3. **Chấm điểm ở server.** Client không có đường nào để tự khai điểm.
4. **Quyết định nộp bài ở server.** Client chỉ nhận lệnh.

→ **Hệ quả:** kể cả thí sinh có source đầy đủ của SEB Client, họ vẫn phải *làm bài thật*. Crack chỉ giúp thoát các ràng buộc UI — mà ràng buộc UI vốn đã là tầng ràng buộc yếu nhất. Đây là điểm phải nói rõ trong báo cáo.

### 2.2 Mô hình đe doạ & biện pháp

| # | Đe doạ | Biện pháp | Mức | Ghi chú trung thực |
|---|---|---|---|---|
| C1 | Giả mạo header `X-Client-Type: seb` bằng curl | Challenge HMAC nonce 1-lần; `device_secret` dẫn xuất từ salt + `SECRET_KEY`, **không lưu rõ trong DB** | **Cao** | Kẻ tấn công phải đăng nhập hợp lệ bằng tài khoản thi thật. *Đã triển khai.* |
| C2 | Replay request đã bắt được | Nonce TTL 30 s, dùng 1 lần xoá ngay; HMAC phủ cả `nonce\|version\|fingerprint` | **Cao** | *Đã triển khai + test.* |
| C3 | Đọc đáp án từ traffic | `QuestionPublic` không có `is_correct` | **Cao** | — |
| C4 | Sửa binary / patch file `.exe` | **Self-check hash**: client so `sha256` của file đang chạy với giá trị nhúng trong chính nó | **Trung bình** | Tự tham chiếu → người giỏi bypass được. Đây là rào chắn chặn gian lận ở mức đồ án, không phải DRM thương mại |
| C5 | Debugger (OllyDbg/x64dbg/IDA/GDB/LLDB) | `IsDebuggerPresent` / `sysctl P_TRACED` / `/proc/self/status`; nếu phát hiện → **từ chối vào phòng thi + báo server** | **Thấp–TB** | Chỉ chặn được debug cấp người dùng. Kernel debugger bypass được. **Không được tuyên bố chống được** |
| C6 | Đóng gói lại bản "đã patch" và phát cho nhau | **Code signing**: ký số binary (Windows Authenticode / macOS codesign notarize / Linux). Client kiểm chữ ký trước khi chạy; server từ chối `client_hash` không nằm trong danh sách đã ký | **TB–Cao** | Đây là biện pháp đáng tiền nhất |
| C7 | Đọc source để hiểu cấu trúc | Build bằng **Nuitka** (biên dịch Python → C) thay vì PyInstaller (chỉ nén bytecode) | **TB** | Tốn thời gian build hơn; dùng cho bản release, giữ bản source để dev |
| C8 | Chạy client trên máy ảo để lách | Phát hiện VM/sandbox (CPUID hypervisor bit, tên file registry `VMwareTools`, MAC OUI, tốc độ CPU…) → cảnh báo + ghi log, **không tự động đuổi** | **Thấp** | Dễ bypass. Giá trị nằm ở **bằng chứng** cho hội đồng |
| C9 | Chạy nhiều phiên / đăng nhập trùng | `DuplicateLoginGuard` phía server: 1 session active / 1 fingerprint; lần 2 → `DUPLICATE_LOGIN` + buộc kick | **Cao** | Đây là biện pháp server-side nên không thể bypass bằng patch client |
| C10 | Ngắt mạng để né heartbeat | Server đánh dấu `DISCONNECTED` sau 30 s; hết thời gian grace → `AUTO_TIMEOUT` | **Cao** | Đã có sẵn |
| C11 | Sửa đồng hồ máy | **Server giữ đồng hồ chuẩn** (Quy tắc #4.1). Client chỉ nhận `server_time` + `deadline` để đếm đồng hồ | **Cao** | Đã có sẵn |

> Bảng này sẽ vào báo cáo gần như nguyên văn, cột "Ghi chú trung thực" là phần **quan trọng nhất** — thể hiện độ trung thực học thuật theo Quy tắc #5.

### 2.3 Danh sách công việc

**2.3.1 Challenge-response (đã nằm trong Phase 0, phần cốt lõi)**
- [ ] Bảng `client_attestations` (session_id, nonce_hash, client_version, fingerprint, signed_at, verified)
- [ ] `attestation_service.py`: `issue_nonce()`, `verify_signature()`, `issue_session_secret()`
- [ ] `dependencies/client_identity.py`: đọc + xác minh header ở mọi endpoint nhạy cảm

**2.3.2 Integrity & anti-tamper**
- [ ] `integrity/self_check.py` — tính SHA-256 file đang chạy, so với giá trị nhúng; lệch → từ chối + báo
- [ ] `integrity/anti_debug.py` — 3 adapter theo OS, đăng ký vào `capability_matrix`
- [ ] `integrity/license_check.py` — kiểm tra `seb_client_config.min_version` từ server; client cũ hơn → từ chối nâng cấp
- [ ] Gửi `client_hash` + `client_version` + `signed` lên server mỗi lần vào phòng; server lưu và đối chiếu danh sách hash hợp lệ

**2.3.3 Hardening build**
- [ ] `packaging/build_windows.ps1` — Nuitka compile + PyInstaller (chọn 1) + `signtool sign`
- [ ] `packaging/build_macos.sh` — Nuitka + `codesign --deep --force` + `notarytool submit`
- [ ] `packaging/build_linux.sh` — Nuitka + `sha256sum` + công bố hash
- [ ] Tắt mọi `assert`, bỏ log dài, không nhúng URL/secret vào binary
- [ ] Dependency pin chính xác trong `requirements.txt` (`==`), sinh `requirements-lock.txt`

**2.3.4 Phía server bổ sung**
- [ ] `exam_sessions`: thêm `client_type`, `client_version`, `client_hash`, `attestation_status`, `device_fingerprint`
- [ ] Bảng `signed_client_releases` (version, hash, os, released_at) — GV đăng ký bản hợp lệ
- [ ] `attestation_service.raise_alert()` khi client chưa attest nhưng cờ `require_safe_browser` đang bật

### 2.4 Tiêu chí hoàn thành Phase 2

- [ ] `curl` giả header `X-Client-Type: seb` → server **từ chối** phiên thi với `attestation_status = FAILED`.
- [ ] Sửa 1 byte trong binary → client từ chối chạy.
- [ ] Chạy binary không ký → server ghi nhận vào log hệ thống.
- [ ] Chạy 2 instance cùng tài khoản → `DUPLICATE_LOGIN`, kick bản cũ.
- [ ] Lấy traffic HTTPS → không thấy `is_correct`.
- [ ] Bảng 2.2 được đưa vào báo cáo kèm cột ghi chú trung thực.

---

## PHASE 3 — Test, đóng gói & tài liệu

### 3.1 Kiểm thử

| Hạng mục | Công cụ | Ghi chú |
|---|---|---|
| Unit test service | `pytest` + `httpx` | Đã có sẵn trong `backend/tests/` |
| Unit test guard | `pytest` | Thêm mới ở `seb_client/tests/` |
| API test | `pytest` | Cover: toggle bật/tắt, nonce 1-lần, ngưỡng vi phạm |
| Load test | `locust` (miễn phí) | Mô phỏng 200–500 thí sinh đồng thời |
| E2E | `pytest` + Playwright | Luồng login → vào phòng → làm bài → nộp |
| Ma trận OS | Test tay | Windows 10/11, macOS 14+, Ubuntu 22.04 (X11) + Ubuntu 24.04 (Wayland) |
| Test chống crack | Kịch bản C1–C11 | Làm thật, ghi kết quả vào báo cáo |

### 3.2 Tài liệu phải cập nhật (theo Quy tắc #2.2 & #10)

- [ ] **SRS v3** — bổ sung mục về SEB Client, `require_safe_browser`, challenge-response, bảng 2.2
- [ ] **`skills.md` v3.0** — sửa Quy tắc #1 & #2 cho khớp phạm vi mới (xem `docs/PLAN.md` mục 5)
- [ ] `README.md` — hướng dẫn chạy web, chạy client, đóng gói
- [ ] `docs/ERD.md` — cập nhật 2 bảng mới
- [ ] `docs/BAOCAO_LIMITATION.md` — **bắt buộc** (Quy tắc #5)

### 3.3 Báo cáo đồ án — phần bắt buộc phải có

1. **Bảng so sánh 2 lớp**: web làm được gì / không làm được gì; client làm thêm được gì.
2. **Ma trận năng lực theo OS** (mục 1.3) — nêu rõ ô trống.
3. **Bảng 2.2 mô hình đe doạ** — kèm cột ghi chú trung thực.
4. **Mục "Giới hạn kỹ thuật"** — nói thẳng:
   - Không thể chống crack 100% với phần mềm chạy trên máy thí sinh.
   - `Alt+Tab` trên Windows client: **phát hiện được trong ~300 ms**, nhưng vẫn là hành vi **đã xảy ra rồi mới biết**, không phải ngăn chặn.
   - Debugger cấp kernel, thiết bị thứ hai, camera phim tay trước màn hình: **nằm ngoài khả năng kỹ thuật của đồ án.**
   - Wayland hạn chế nhiều cơ chế giám sát cửa sổ.

---

## 5. Cập nhật `skills.md` (bắt buộc)

Để `skills.md` không mâu thuẫn với plan này, cần sửa:

| Mục | Sửa thành |
|---|---|
| **Quy tắc #1** | Đổi từ "CHỈ LÀM WEBSITE, KHÔNG LÀM BROWSER" → "HAI LỚP SONG SONG: Web (bắt buộc) + SEB Client (PySide6, nâng cao). Cấm Electron/Tauri/CEF nhúng và cấm viết bằng ngôn ngữ khác Python cho client." |
| **Quy tắc #2** | Thêm hàng vào bảng: *SEB Client desktop* → `PySide6 + Qt WebEngine`; *đóng gói client* → `Nuitka` (release) / `PyInstaller` (dev); *ký số* → `signtool` / `codesign` / `sha256sum`. |
| **Quy tắc #2.4** | Sửa mục "❌ KHÔNG dùng Python cho…" — bỏ cấm PySide6, thay bằng: *"Dùng cho client chỉ trong phạm vi `seb_client/`"*. |
| **Quy tắc #6** | Thêm `seb_client/` vào sơ đồ cấu trúc. |
| **Quy tắc #3** | Bổ sung nhóm 3: cơ chế chỉ client mới có (foreground window, clipboard hệ thống, VM detect). Vẫn ghi log qua `logViolation`. |
| **Quy tắc #7** | Bổ sung `system_settings`, `exam_security_configs`, `client_attestations`, `signed_client_releases`. |
| **Quy tắc #5** | Giữ nguyên, bổ sung: cột "Ghi chú trung thực" trong bảng mô hình đe doạ là bắt buộc. |

---

## 6. Ưu tiên & rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Làm client mà không xong web → trượt đề | **Cao** | Phase 0 là điều kiện tiên quyết. Không được sang Phase 1 khi web chưa nộp được. |
| GVHD đổi ý kiến lần nữa | Trung bình | Web **vẫn dùng được 100%** nếu bỏ toàn bộ Phase 1–2. Không xây gì mà web phụ thuộc ngược lại. |
| Qt WebEngine không ổn định trên một số máy | Trung bình | `capability_matrix` + báo cáo OS không hỗ trợ, có đường fallback về web hạn chế |
| Nuitka build chậm / lỗi trên máy khác | Thấp | Build trên CI hoặc 1 máy build cố định, phát hành bản `.exe`/`.dmg`/`.AppImage` sẵn |
| Wayland giới hạn nhiều | Trung bình | Nêu rõ trong báo cáo; khuyến nghị phòng thi dùng Windows |
| Hết giờ làm đồ án | Cao | Mỗi Phase có tiêu chí hoàn thành rõ ràng, dừng được sau Phase 0 |

**Khuyến nghị thứ tự nộp:** nộp **Phase 0** trước. Phase 1–2 là phần "ăn thêm điểm". Nếu thời gian khan, dừng sau Phase 0 vẫn là một đồ án hoàn chỉnh hợp lệ.
