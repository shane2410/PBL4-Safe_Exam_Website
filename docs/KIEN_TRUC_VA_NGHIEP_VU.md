# TÀI LIỆU KIẾN TRÚC & NGHIỆP VỤ
## Hệ thống Thi trắc nghiệm trực tuyến An toàn (PBL4 — Secure Online Exam System)

> Tài liệu này tổng hợp từ **mã nguồn thực tế** (backend / frontend / SEB Client) và
> **knowledge graph** (`graphify-out/graph.json`, 2050 node · 5455 cạnh · 115 cộng đồng).
> Mọi con số, tên hàm, đường dẫn đều đối chiếu trực tiếp với code, không suy diễn.
>
> **Cách đọc:** nếu mới tiếp cận, đọc theo thứ tự
> [1.1 Từ điển thuật ngữ](#11-từ-điển-thuật-ngữ-đọc-trước-khi-đọc-phần-còn-lại) →
> [1.2 Request đi qua hệ thống](#12-đọc-một-request-đi-qua-hệ-thống) →
> [2.3 Sơ đồ tuần tự](#23-sơ-đồ-tuần-tự-một-ca-thi-trọn-vẹn) →
> [12 Vòng đời phiên thi](#12-vòng-đời-một-phiên-thi). Bốn mục đó cho bức tranh
> tổng thể; các chương còn lại là chi tiết từng tầng.
>
> Phiên bản tài liệu: 2026-11-12 · Đối chiếu code sau các bản vá P0 (fullscreen,
> header webview, kết thúc kiosk).

---

## MỤC LỤC

- **Nhập môn** — đọc trước tiên
  - [1. Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
    - [1.1. Từ điển thuật ngữ](#11-từ-điển-thuật-ngữ-đọc-trước-khi-đọc-phần-còn-lại)
    - [1.2. Một request đi qua hệ thống](#12-đọc-một-request-đi-qua-hệ-thống)
    - [1.3. Ranh giới trách nhiệm](#13-ranh-giới-trách-nhiệm-giữa-các-tầng)
  - [2. Sơ đồ kiến trúc](#2-sơ-đồ-kiến-trúc)
    - [2.1. Một tiến trình, hai giao thức, ba client](#21-một-tiến-trình-hai-giao-thức-ba-client)
    - [2.2. Trạng thái sống ở đâu](#22-trạng-thái-sống-ở-đâu)
    - [2.3. Sơ đồ tuần tự một ca thi](#23-sơ-đồ-tuần-tự-một-ca-thi-trọn-vẹn)
- **Từng tầng**
  - [3. Công nghệ & thư viện](#3-công-nghệ--thư-viện-đã-dùng)
  - [4. Mô hình dữ liệu](#4-mô-hình-dữ-liệu) — [state machine](#42-trạng-thái-phiên-thi-examsessionsstatus), [loại nộp bài](#43-loại-nộp-bài-submittype), [cột dễ nhầm](#45-các-cột-có-thể-gây-hiểu-nhầm)
  - [5. Module backend](#5-các-module-backend) — [endpoint mẫu](#58-một-endpoint-trông-như-thế-nào), [luồng service](#59-luồng-phụ-thuộc-giữa-các-service)
  - [6. Module frontend](#6-các-module-frontend-lớp-a--web) — [state machine ExamRoom](#65-state-machine-của-examroom), [F5 giữa giờ](#67-điều-gì-xảy-ra-khi-f5-giữa-giờ-thi)
  - [7. SEB Client](#7-seb-client-lớp-b--desktop) — [interceptor](#76-vì-sao-webview-cần-clientidentityinterceptor), [giới hạn từng guard](#77-chi-tiết-từng-guard--chặn-được-gì-không-chặn-được-gì), [vòng đời cửa sổ](#78-vòng-đời-một-cửa-sổ-thi)
  - [8. Socket.IO](#8-socketio--giao-thức-thời-gian-thực) — [bảng sự kiện](#87-bảng-sự-kiện-đầy-đủ-đối-chiếu-code), [vì sao `embedded=1`](#88-vì-sao-embedded1-phải-có)
- **Nghiệp vụ & vận hành**
  - [9. Logic nghiệp vụ](#9-logic-nghiệp-vụ-cốt-lõi)
  - [10. Bảo mật nhiều lớp](#10-cơ-chế-bảo-mật-nhiều-lớp)
  - [11. Tiến trình nền](#11-các-tiến-trình-nền) — [cuộc đua 3 bên khi hết giờ](#111-ai-nộp-bài-khi-hết-giờ--cuộc-đua-3-bên)
  - [12. Vòng đời một phiên thi](#12-vòng-đời-một-phiên-thi)
  - [13. Phân quyền](#13-phân-quyền)
  - [14. Danh mục API](#14-danh-mục-api)
  - [15. Cấu hình & triển khai](#15-cấu-hình--triển-khai)
  - [16. Giới hạn kỹ thuật](#16-giới-hạn-kỹ-thuật-trung-thực)
- **Phụ lục**
  - [A. Bản đồ mã nguồn](#phụ-lục-a--bản-đồ-mã-nguồn-nhanh)
  - [B. Điểm nối giữa các lớp](#phụ-lục-b--điểm-nối-giữa-các-lớp)
  - [C. Câu hỏi thường gặp khi đọc code](#phụ-lục-c--câu-hỏi-thường-gặp-khi-đọc-code)

---

## 1. Tổng quan hệ thống

Hệ thống thi trắc nghiệm trực tuyến có cơ chế **khoá an toàn** và **giám sát thời
gian thực**, lấy cảm hứng từ mô hình nghiệp vụ Safe Exam Browser (SEB).

Điểm khác biệt cốt lõi so với một hệ thống thi thông thường: **bảo vệ hai lớp**.

| Lớp | Tên | Bản chất | Điểm mạnh | Điểm yếu |
|---|---|---|---|---|
| **Lớp A** | Web app (React) | Chạy trong trình duyệt | Triển khai nhanh, không cài đặt | Chỉ chặn được trong phạm vi tab; người dùng bỏ qua được |
| **Lớp B** | SEB Client (PySide6) | Ứng dụng desktop, có chữ ký thiết bị | Chặn ở tầng hệ điều hành (Alt+Tab, taskbar, clipboard) | Cần cài đặt; vẫn thua kẻ chiếm quyền máy |

Hai lớp đọc **cùng một nguồn cấu hình** (`ExamSecurityService.resolve_policy`) nên
không thể lệch nhau về cơ chế bật/tắt.

**Nguyên tắc thiết kế xuyên suốt** (được ghi trong code):
- *Server là nguồn sự thật duy nhất* về thời gian, mức nghiêm trọng vi phạm và
  quyết định thu bài. Client không bao giờ tự quyết định điểm hay hình phạt.
- *Thiếu thì báo thiếu* — nền tảng không hỗ trợ cơ chế nào phải khai báo rõ cho
  giảng viên, không giả vờ đang bảo vệ.
- *Tắt cờ trong DB là thực sự tắt* — mọi guard đọc policy từ server, không hardcode.

### 1.1. Từ điển thuật ngữ (đọc trước khi đọc phần còn lại)

Các từ dưới đây xuất hiện xuyên suốt tài liệu và trong tên biến của mã nguồn. Hiểu
sai một từ là hiểu sai cả một cơ chế.

| Thuật ngữ | Nghĩa chính xác trong dự án | Xuất hiện ở |
|---|---|---|
| **Đề (exam)** | Bộ câu hỏi + thời lượng + điểm. Chưa có giờ, chưa có phòng. | `exams` |
| **Ca thi (schedule)** | Một lần tổ chức đề: `room_code`, `start_time`, `end_time`, giảng viên phụ trách. | `exam_schedules` |
| **Phiên (session)** | Một thí sinh làm một ca. Sinh ra khi gọi `join`, giữ `session_token`, điểm, bộ đếm vi phạm. | `exam_sessions` |
| **Mã phòng (`room_code`)** | Chuỗi thí sinh gõ để vào ca thi, VD `PBL4-EXAM-01`. Unique toàn hệ thống. | `exam_schedules.room_code` |
| **`session_token`** | Chuỗi `sess_<uuid4>` định danh **phiên**, không phải người. Dùng cho socket, save-answer, submit. | `exam_sessions.session_token` |
| **Policy** | `ExamSecurityConfig`: 12 field bật/tắt cơ chế khoá. Server resolve rồi trả cho client. | `settings_schema.py` |
| **Guard** | Một lớp chặn/phát hiện một hành vi cụ thể. Lớp B có 7 guard. | `seb_client/sebclient/guards/` |
| **Hook** | Cùng ý niệm guard nhưng viết cho React. Lớp A có 8 hook. | `frontend/src/pages/exam/hooks/` |
| **Attestation** | Chứng minh "request này đến từ đúng ứng dụng SEB trên đúng thiết bị", bằng chữ ký Ed25519. | `attestation_service.py` |
| **`device_id`** | `sha256(public_key)[:16]` — định danh thiết bị, ổn định, không lấy từ MAC/hostname. | `client_devices` |
| **`device_fingerprint`** | `sha256(public_key)` đầy đủ 64 ký tự — ràng buộc attestation token với máy. | header `X-Device-Fingerprint` |
| **Ngưỡng (threshold)** | Tổng `max_tab_switch + max_fullscreen_exit`. Vượt → tự nộp `AUTO_VIOLATION`. | `anticheat_service.py` |
| **Risk score** | Điểm rủi ro tích luỹ (0–1000) để giảng viên xếp hạng, **không** phải điều kiện nộp bài. | `exam_sessions.risk_score` |
| **`restricted_mode`** | Đề bắt buộc SEB nhưng request hiện tại chưa chứng minh được → vẫn cho thi nhưng ghi log. | `join_exam` response |
| **`embedded=1`** | Tham số URL nói với trang web: "mày đang chạy trong SEB, đừng tự mở socket". | `useSecurityPolicy.js:39` |
| **Lớp A / Lớp B** | A = web React; B = ứng dụng desktop PySide6. Không phải "layer" theo nghĩa mạng. | toàn tài liệu |
| **Sweeper** | Vòng quét nền tự nộp phiên quá hạn khi client không nộp. | `deadline_sweeper.py` |

> **Cẩn thận với từ "session".** Trong code có 3 thứ khác nhau cùng tên:
> `ExamSession` (phiên thi, DB), "session" của Socket.IO (`sid`), và session HTTP.
> Khi đọc, luôn xác định đang nói cái nào.

### 1.2. Đọc một request đi qua hệ thống

Phần này là la bàn: mọi mục sau chỉ mô tả chi tiết một chặng của con đường dưới đây.

**Ví dụ A — thí sinh lưu một đáp án** (`POST /api/exam-sessions/save-answer`):

```
[1] React: người dùng tick đáp án
     └─ setAnswers(...)                    ExamRoom.jsx
[2] useAutoSave: debounce 1.5s
     └─ flush() → apiClient.post(...)      useAutoSave.js:20
         ├─ interceptor gắn Authorization: Bearer <JWT>
         └─ interceptor gắn X-Client-Type: web       apiClient.js:18

[3] FastAPI nhận request
     ├─ CORSMiddleware kiểm origin                   main.py:51
     ├─ dependency get_current_user → giải JWT → User
     │                                              dependencies/auth.py:11
     ├─ dependency get_client_identity → đọc header client
     │                                              dependencies/client_identity.py:73
     └─ dependency require_role(["STUDENT",...])     dependencies/auth.py:44

[4] Router chỉ điều phối, không chứa nghiệp vụ
     └─ ExamSessionService.save_answer(db, token, data, user)
                                                    exam_session_router.py

[5] Service kiểm tra theo thứ tự 7 bước
     ├─ phiên tồn tại & chưa SUBMITTED
     ├─ chủ sở hữu
     ├─ ca có đề
     ├─ now > deadline ? → 403
     ├─ question_id thuộc đề
     ├─ option_id thuộc câu
     └─ upsert StudentAnswer
                                                    exam_session_service.py:309

[6] SQLAlchemy ghi DB, trả JSON
[7] React nhận 200 → status "saved" → hiện "Đã lưu"
```

**Ví dụ B — thí sinh chuyển tab, server tự nộp bài.** Chặng này đi qua **socket**,
không phải REST:

```
[1] Trình duyệt bắn visibilitychange
     └─ useVisibilityMonitor → onAway('visibilitychange')
                                                    useVisibilityMonitor.js:27
[2] ExamRoom.handleIncident gộp sự kiện
     ├─ dedupe 1.5s, chặn nếu đã locked hoặc đã đủ ngưỡng
     └─ logViolation('TAB_SWITCH')              ExamRoom.jsx:240
[3] useSecurityPolicy.logViolation
     └─ socket.emit('violation', {...})          useSecurityPolicy.js:92

[4] Socket.IO server: exam_namespace.py
     ├─ sid có trong active_sockets? (đã join_exam_room)
     ├─ event_type nằm trong ALLOWED_EVENT_TYPES?
     └─ AnticheatService.record_violation(...)
[5] record_violation
     ├─ session.status phải IN_PROGRESS
     ├─ ghi ViolationLog (severity SERVER tự quyết)
     ├─ tab_switch_count += 1
     ├─ risk_score += 10 (trần 1000)
     └─ counted = tab_switch + fullscreen_exit
        vượt ngưỡng? → threshold_exceeded = True    anticheat_service.py:63
[6] exam_namespace, nếu vượt ngưỡng
     ├─ policy.auto_submit_on_threshold?
     ├─ submit_exam(AUTO_VIOLATION) → chấm điểm ngay
     ├─ emit 'force_submit'        → CHÍNH thí sinh đó
     └─ emit 'student_force_submitted' → phòng monitor
                                                    exam_namespace.py:238
[7] React nhận force_submit
     └─ handleForceSubmit → setLocked(true) → dừng mọi hook
        → submitExam('AUTO_VIOLATION')               ExamRoom.jsx:171
```

Hai ví dụ này cho thấy quy ước quan trọng: **REST cho thao tác nghiệp vụ, socket
cho sự kiện và quyết định tức thời.** Không bao giờ gửi đáp án qua socket, và
không bao giờ để REST quyết định "thí sinh vi phạm".

### 1.3. Ranh giới trách nhiệm giữa các tầng

| Tầng | Chỉ được làm | Tuyệt đối không làm |
|---|---|---|
| React (Lớp A) | Hiển thị, thu thập input, phát hiện sự kiện trong tab | Tự quyết định điểm, tự kết luận "vi phạm", tự đổi `status` |
| `apiClient` / `socketClient` | Gắn token, gửi/nhận | Chứa logic nghiệp vụ |
| Router (backend) | Validate input, gọi đúng 1 service, trả schema | Truy vấn ORM trực tiếp, tính toán nghiệp vụ |
| Service | Toàn bộ nghiệp vụ + transaction | Biết gì về HTTP, trả `HTTPException` chỉ khi đó là lỗi nghiệp vụ |
| Model | Ánh xạ bảng, quan hệ | Logic nghiệp vụ |
| SEB Client | Chặn/phát hiện ở tầng OS, gửi sự kiện | Quyết định hình phạt, tính điểm |

Quy ước này giải thích vì sao `ExamRoom.jsx` dài 933 dòng nhưng **không có dòng
nào tính điểm**, và vì sao `grading_service.py` không import `fastapi`.

---

## 2. Sơ đồ kiến trúc

```
┌───────────────────────────────────────────────────────────────────────────┐
│                            NGƯỜI DÙNG                                     │
│   Sinh viên (trình duyệt)      Giảng viên      Quản trị viên              │
└──────────────┬──────────────────────┬──────────────────┬──────────────────┘
               │                      │                  │
       ┌───────▼──────────────────────▼──────────────────▼───────┐
       │            LỚP A — WEB APP (React 18 + Vite)            │
       │  Router theo role · Zustand · 8 hook khoá an toàn       │
       │  axios (REST)  ·  socket.io-client (realtime)           │
       └───────┬──────────────────────────────┬─────────────────┘
               │ HTTPS /api                   │ WSS /socket.io
       ┌───────▼──────────────────────────────▼─────────────────┐
       │           BACKEND — FastAPI + python-socketio           │
       │                                                         │
       │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
       │  │   Routers   │→ │   Services   │→ │    Models     │  │
       │  │  (HTTP)     │  │ (nghiệp vụ)  │  │  (SQLAlchemy) │  │
       │  └─────────────┘  └──────────────┘  └───────────────┘  │
       │  ┌──────────────────────┐  ┌─────────────────────────┐  │
       │  │  Sockets (realtime)  │  │ Tiến trình nền (asyncio)│  │
       │  │  exam · monitor      │  │ heartbeat · sweeper     │  │
       │  └──────────────────────┘  └─────────────────────────┘  │
       └───────────────────────────┬─────────────────────────────┘
                                   │ MySQL (SQLAlchemy 2.0)
                          ┌────────▼────────┐
                          │   MySQL / MariaDB│
                          │  16 bảng         │
                          └─────────────────┘

       ┌────────────────────────────────────────────────────────┐
       │        LỚP B — SEB CLIENT (PySide6 + Qt WebEngine)     │
       │  LoginWindow → ExamWindow(QWebEngineView)              │
       │  7 guard: kiosk·keyboard·devtools·clipboard·download·  │
       │           navigation·session                           │
       │  OS adapter: Windows / macOS / Linux(X11|Wayland)      │
       │  Attestation Ed25519 · Socket.IO heartbeat             │
       └────────────────────────────────────────────────────────┘
```

**Giao tiếp:**
- REST (`/api/...`) — thao tác nghiệp vụ, chịu được retry, có thể cache.
- Socket.IO — dữ liệu **đẩy** (violation alert, force submit, trạng thái thí sinh)
  và **nhịp sống** (heartbeat mỗi 10s). Không dùng cho thao tác nghiệp vụ quan trọng.

### 2.1. Một tiến trình, hai giao thức, ba client

Điểm dễ hiểu sai nhất: **REST API và Socket.IO chạy trên CÙNG một cổng**. Không có
server thứ hai, không có broker.

```python
# backend/app/main.py:111
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)
```

`ASGIApp` kiểm tra đường dẫn: nếu là `/socket.io/...` thì đưa cho `sio`, còn lại
đẩy sang `fastapi_app`. Vì vậy:

| Cổng dev | Cổng prod | Phục vụ |
|---|---|---|
| `8000` | `443` (qua nginx) | `/api/*` (REST) + `/socket.io/*` (WS) + `/docs` |
| `5173` | `443` (nginx trả file tĩnh) | Bundle React đã build |

**Ba loại client** kết nối tới cùng backend đó:

| Client | Xác thực | Giao thức dùng | Vòng đời |
|---|---|---|---|
| Trình duyệt (thí sinh) | JWT trong header | REST + Socket | Đóng tab là hết |
| Trình duyệt (GV/QTV) | JWT trong header | REST + Socket (monitor) | Đóng tab là hết |
| SEB Client | JWT + Ed25519 | REST + Socket + **nhúng webview** | Tắt app mới hết |

SEB Client đặc biệt: nó vừa là client của backend, vừa là **vỏ bọc** cho một client
khác (trang web). Đó là lý do có tham số `embedded=1` — trang web bên trong phải
biết mình không nên tự mở socket, nếu không sẽ có 2 kết nối cho 1 phiên.

```
                SEB Client (một process duy nhất)
   ┌──────────────────────────────────────────────────────────┐
   │                                                          │
   │   ApiClient (httpx) ─────────────────────── REST ──┐     │
   │   ExamSocket  ────────────────────────────── WS ──┐│     │
   │                                                    ││     │
   │   ┌──────────────────────────────────────────────┐ ││     │
   │   │ QWebEngineView (Chromium nhúng)              │ ││     │
   │   │   React app ───── REST + WS ─────────────────┼─┘│     │
   │   │   URL có &embedded=1  (KHÔNG tự mở socket)   │  │     │
   │   └──────────────────────────────────────────────┘  │     │
   └─────────────────────────────────────────────────────┼─────┘
                                                         ▼
                                                   Backend :8000
```

Trang web trong webview **vẫn gọi backend trực tiếp** — nó không đi qua `ApiClient`
của Python. Đó là lý do phải có `ClientIdentityInterceptor` gắn header định danh
(xem mục 7.6): nếu không, request của trang web trông y hệt request từ Chrome thường.

### 2.2. Trạng thái sống ở đâu

Đây là câu hỏi hay gặp khi debug "tại sao restart server thì mất X".

| Dữ liệu | Sống ở | Mất khi | Ghi chú |
|---|---|---|---|
| Người dùng, đề, ca, phiên, đáp án, vi phạm | MySQL | Xoá DB | Nguồn sự thật |
| `active_sockets[sid]` | RAM backend | Restart backend | Heartbeat monitor đọc đây |
| `_pending_nonces` | RAM backend | Restart backend | Nonce attestation, TTL 30s |
| `_identities[sid]` | RAM backend | Restart backend | `sid → {user_id, role}` |
| Preview import `.docx` | RAM backend | Restart / hết 30 phút | Token + danh sách câu |
| JWT của người dùng | `localStorage` | Đăng xuất / 401 | Client tự gửi kèm |
| `session_token` | RAM React / DB | Đóng tab vẫn còn trong DB | React lấy lại qua `join` |
| Private key Ed25519 | Kho hệ thống (DPAPI/Keychain/SecretService) | Xoá máy | **Không bao giờ** gửi lên server |
| Attestation token | RAM client | 5 phút | Client tự attest lại mỗi 4 phút |
| Policy đang áp dụng | DB + RAM client | F5 thì lấy lại | Client không được tự sửa |

Hệ quả thực tế: **restart backend giữa giờ thi** làm mất `active_sockets`, nên
heartbeat monitor không còn gì để quét và giám sát hiện danh sách rỗng cho tới khi
thí sinh reconnect. Phiên trong DB vẫn `IN_PROGRESS` và đáp án đã lưu vẫn còn — chỉ
mất phần realtime. Đây là lý do tài liệu triển khai yêu cầu không restart khi đang thi.

### 2.3. Sơ đồ tuần tự: một ca thi trọn vẹn

**Chuẩn bị (trước giờ thi, một lần):**

```
Giảng viên            Backend
    │                    │
    ├─ POST /exams ─────▶│ tạo đề (chưa có giờ)
    ├─ PUT /exams/{id}/security-policy ─▶│ 12 cờ cơ chế khoá
    ├─ POST /exams/schedules ───────────▶│ tạo ca, sinh room_code
    │                    │               (VD "PBL4-EXAM-01")
Admin                 Backend
    ├─ PUT /admin/settings/require-safe-browser {"value":true} ─▶│ cờ toàn cục
```

Hiệu lực cuối cùng của "chỉ cho phép SEB" = **cờ đề AND cờ hệ thống**. GV tắt ở
đề thì đề đó vẫn thi bằng web được dù hệ thống đang bật.

**Thi bằng web (Lớp A):**

```
Thí sinh(web)              Backend                  Monitor(GV)
    │                         │                          │
    ├─ POST join {room_code} ▶│                          │
    │                         ├─ check_exam_schedule_active
    │                         ├─ resolve_policy(exam)
    │                         ├─ upsert ExamSession      │
    │  ◀── đề + policy + bộ đếm ─────────────────────────┤
    │                         │                          │
    ├─ socket connect(auth=JWT) ▶│                       │
    ├─ emit join_exam_room ───▶│ vào room_<CODE>          │
    │                         ├─ emit student_status ────▶│
    │                         │                          │
    ├─ Bấm "Bắt đầu thi"      │                          │
    │   → fullscreen          │                          │
    │   → bật 8 hook          │                          │
    │                         │                          │
    ├─ chọn đáp án            │                          │
    │   (debounce 1.5s)       │                          │
    ├─ POST save-answer ─────▶│ ghi StudentAnswer        │
    │                         │                          │
    ├─ emit heartbeat (10s) ─▶│ cập nhật last_heartbeat  │
    │                         │                          │
    ├─ rời tab                │                          │
    ├─ emit violation ───────▶│ ghi ViolationLog         │
    │                         ├─ risk_score += 10        │
    │                         ├─ tab_switch_count += 1   │
    │                         ├─ emit violation_alert ──▶│
    │                         │                          │
    │                         │  [vượt ngưỡng]           │
    │  ◀── force_submit ──────┤                          │
    │   (khoá UI)             ├─ submit AUTO_VIOLATION   │
    │                         ├─ grade_session()         │
    │                         ├─ emit student_force_submitted ▶│
    │                         │                          │
    ├─ (hoặc) bấm "Nộp bài"   │                          │
    ├─ flush đáp án ─────────▶│                          │
    ├─ POST submit(MANUAL) ──▶│ grade_session()          │
    │  ◀── điểm, risk, bộ đếm │                          │
    │                         │                          │
    │  [hết giờ nếu không ai nộp — sweeper quét mỗi 30s] │
    │                         ├─ submit AUTO_TIMEOUT     │
```

**Thi bằng SEB Client (Lớp B):** thêm 4 bước trước `join`, phần còn lại giống hệt
(vì webview bên trong vẫn gọi đúng các API đó).

```
SEB Client                     Backend
    │                             │
    ├─ POST /auth/client-devices ▶│ đăng ký public key (1 lần/thiết bị)
    │  ◀── device_id              │
    ├─ POST /auth/client-nonce ──▶│ nonce, TTL 30s
    │  ◀── nonce                  │
    ├─ ký Ed25519(private_key, "nonce|version|fingerprint|device_id")
    ├─ POST /auth/client-attest ─▶│ verify bằng public key
    │  ◀── attestation_token      │  (TTL 5 phút)
    │                             │
    ├─ POST join {room_code} ────▶│ kèm header X-Attestation-Token
    │                             ├─ is_verified_seb = True
    │  ◀── đề + policy, restricted_mode = false
    │                             │
    ├─ socket connect + join_exam_room
    ├─ QWebEngineView.load(URL có &embedded=1)
    │     └─ React bên trong KHÔNG mở socket riêng
    ├─ (QTimer 240s) attest lại → token không hết hạn giữa giờ
```

**Điểm khác biệt cốt lõi giữa hai nhánh:** SEB Client **tự** gửi sự kiện vi phạm
ở tầng OS (Alt+Tab, clipboard, ẩn taskbar), mạnh hơn hook DOM. Vì vậy khi
`embedded=1`, trang web ngừng gửi để tránh đếm hai lần.

---

## 3. Công nghệ & thư viện đã dùng

### 3.1. Backend (`backend/requirements.txt`)

| Thư viện | Vai trò trong dự án |
|---|---|
| `fastapi` | Web framework ASGI, sinh OpenAPI tự động |
| `uvicorn[standard]` | ASGI server chạy FastAPI |
| `python-multipart` | Nhận `multipart/form-data` cho upload file `.docx` |
| `SQLAlchemy 2.0` | ORM, `joinedload`/`selectinload` chống N+1 |
| `alembic` | Migration (5 phiên bản trong `backend/alembic/versions`) |
| `pymysql` | Driver MySQL cho SQLAlchemy |
| `cryptography` | Ed25519 (xác thực thiết bị) |
| `pydantic` / `pydantic-settings` | Validate schema + đọc config từ env |
| `email-validator` | Validate trường `EmailStr` |
| `python-socketio` | Socket.IO server (chế độ ASGI) |
| `PyJWT` | Sinh/giải mã JWT |
| `passlib[bcrypt]` + `bcrypt` | Hash mật khẩu |
| `slowapi` | Có trong requirements (rate limit; hiện chưa gắn vào router) |
| `python-docx` | Đọc file `.docx` khi import câu hỏi |
| `openpyxl` | Xuất báo cáo Excel |
| `reportlab` | Xuất báo cáo PDF |
| `pytest` / `pytest-asyncio` / `httpx` | Test (hiện 120 test backend) |

### 3.2. Frontend (`frontend/package.json`)

| Thư viện | Vai trò |
|---|---|
| `react` 18 + `react-dom` | UI |
| `react-router-dom` 6 | Định tuyến theo role |
| `zustand` 5 | Store đăng nhập (`authStore.js`) |
| `socket.io-client` 4 | Nhận sự kiện realtime |
| `axios` | HTTP client + interceptor gắn JWT |
| `vite` 5 | Build tool + dev server + proxy |
| `tailwindcss` 3 | Styling (design system riêng theo `design.md`) |
| `eslint` + plugin react/hooks | Lint (chạy với `--max-warnings 0`) |

### 3.3. SEB Client (`seb_client/`)

| Thư viện | Vai trò |
|---|---|
| `PySide6` (Qt 6) | UI desktop, `QWebEngineView` nhúng web app |
| `qasync` | Chạy Qt **trong** asyncio loop (bắt buộc: mạng là async) |
| `httpx` | HTTP async tới backend |
| `python-socketio` (client) | Heartbeat + nhận `force_submit` |
| `cryptography` | Ed25519: sinh khoá, ký challenge |
| `ctypes` (stdlib) | Gọi Win32 API trực tiếp (không phụ thuộc pywin32) |
| `pywin32` (tuỳ chọn) | Chặn máy in trên Windows |

---

## 4. Mô hình dữ liệu

16 bảng, chia 5 nhóm. Quan hệ chính:

```
Role 1───n User
             │
Subject 1───n Question 1───n QuestionOption
   │             │
   │             └──n ExamQuestion n──┐
   │                                  │
   └──n Exam 1───────────────────────┘
          │ 1───1 ExamSecurityConfig
          │
          1──n ExamSchedule ──(supervised_by)── User
                  │
                  1──n ExamSession ──(student_id)── User
                          │
                          ├──n StudentAnswer ─n─ Question
                          ├──n ViolationLog
                          └──n ClientAttestation

ClientDevice (user_id) ── liên kết qua device_id với ClientAttestation
SystemSetting (key/value JSON)  ·  AuditLog
```

### 4.1. Chi tiết từng bảng

| Bảng | Cột quan trọng | Ghi chú nghiệp vụ |
|---|---|---|
| `roles` | `code` (ADMIN/TEACHER/STUDENT) | 3 vai trò cố định |
| `users` | `username`, `password_hash`, `role_id`, `student_code`, `device_secret_salt` | `is_active` để khoá tài khoản |
| `subjects` | `code`, `name` | Môn học / ngân hàng câu hỏi |
| `questions` | `content`, `type`, `difficulty`, `subject_id`, `created_by` | `type`: SINGLE_CHOICE / MULTI_CHOICE / FILL_BLANK |
| `question_options` | `content`, `is_correct`, `order_index` | `is_correct` **không bao giờ** trả cho client khi thi |
| `exams` | `duration_minutes`, `total_score`, `is_shuffled`, `max_violation_allowed`, `require_safe_browser`, `created_by` | `max_violation_allowed` là bậc 2 của ngưỡng vi phạm |
| `exam_questions` | `exam_id`, `question_id`, `score`, `order_index` | Điểm **theo đề**, không theo câu |
| `exam_security_configs` | `exam_id` (unique), `config` (JSON) | Lưu nguyên `ExamSecurityConfig` đã validate |
| `exam_schedules` | `room_code` (unique), `start_time`, `end_time`, `supervised_by`, `status` | `room_code` là mã phòng thí sinh nhập |
| `exam_sessions` | `session_token`, `started_at`, `status`, `submit_type`, `risk_score`, `tab_switch_count`, `fullscreen_exit_count`, `final_score`, `client_type`, `device_id`, `attestation_status` | Unique `(schedule_id, student_id)` — 1 thí sinh 1 phiên/ca |
| `student_answers` | `selected_option_ids` (JSON), `fill_blank_text`, `auto_score` | Lưu theo từng câu, cập nhật liên tục |
| `violation_logs` | `event_type`, `severity`, `detail` (JSON), `client_timestamp`, `server_timestamp` | `server_timestamp` là thời điểm chuẩn; client chỉ để đối chiếu |
| `client_devices` | `device_id` (= sha256(pubkey)[:16]), `public_key`, `revoked_at` | Chỉ giữ **public key** |
| `client_attestations` | `session_id`, `device_fingerprint`, `verified`, `key_salt` | Vết xác thực client cho từng phiên |
| `system_settings` | `setting_key`, `setting_value` (JSON) | Cấu hình cấp hệ thống |
| `audit_logs` | `action`, `user_id`, `ip_address` | Nhật ký thao tác quản trị |

### 4.2. Trạng thái phiên thi (`exam_sessions.status`)

```
                    ┌──────────────────────────────┐
                    │        IN_PROGRESS           │
                    │  - đang làm bài              │
                    │  - record_violation CÓ ghi   │
                    └───┬──────────────────────┬───┘
                        │                      │
        heartbeat im lặng│                      │ submit (mọi loại)
              > 30s     │                      │
                        ▼                      ▼
              ┌──────────────────┐    ┌──────────────────┐
              │  DISCONNECTED    │    │    SUBMITTED     │
              │ - mất kết nối    │    │ - đã chấm điểm   │
              │ - record_violation│   │ - KHÔNG ghi thêm │
              │   TỪ CHỐI ghi    │    │   vi phạm nữa    │
              └────────┬─────────┘    └──────────────────┘
                       │                     ▲
                       │ join lại            │ sweeper
                       └─────────────────────┘
```

Ba chi tiết quan trọng mà sơ đồ không nói hết:

1. **`DISCONNECTED` không phải trạng thái kết thúc.** Thí sinh vào lại bằng `join`
   là về `IN_PROGRESS` (`exam_session_service.py:151`). Nếu thiếu đoạn chuyển này,
   `record_violation` (yêu cầu `status == IN_PROGRESS`) sẽ **bỏ qua im lặng mọi vi
   phạm còn lại**, và ngưỡng tự nộp không bao giờ kích hoạt nữa. Đây từng là lỗi thật.

2. **`record_violation` có cổng chặn ở đầu hàm**:
   ```python
   if not session or session.status != "IN_PROGRESS":
       return None, False
   ```
   Nên sau khi `SUBMITTED`, mọi vi phạm đến muộn đều bị nuốt. Đó là lý do UI phải
   dừng đếm ngay khi `locked` — không thì thí sinh thấy "15/8" trong khi server đứng ở 8.

3. **Heartbeat monitor đổi trạng thái SAU khi ghi vi phạm.** Thứ tự có chủ đích:
   ghi `CONNECTION_LOST` trước (lúc còn `IN_PROGRESS`), rồi mới đặt `DISCONNECTED`.
   Làm ngược lại thì bằng chứng mất kết nối không bao giờ được ghi.

### 4.3. Loại nộp bài (`submit_type`)

| Giá trị | Ai phát | Khi nào | `submitted_at` |
|---|---|---|---|
| `MANUAL` | Thí sinh | Bấm "Nộp bài" rồi xác nhận | Giờ server |
| `SHUTDOWN_BUTTON` | SEB Client | Thí sinh dùng nút thoát của client | Giờ server |
| `AUTO_TIMEOUT` | React / SEB Client / sweeper | Đồng hồ về 0, hoặc quá hạn + 15s | Giờ server |
| `AUTO_VIOLATION` | Server (socket) | Vượt ngưỡng, hoặc giám thị bấm "Thu bài" | Giờ server |

Giá trị lạ do client gửi lên được **chuẩn hoá thành `MANUAL`** kèm log
(`exam_session_service.py:414`) — không trả 422, vì nộp bài là thao tác không được
phép thất bại chỉ vì một trường enum sai.

`submit_type` là **idempotent**: gọi lại trên phiên đã `SUBMITTED` trả kết quả cũ,
không chấm lại, không ghi đè `submitted_at`. Nhờ vậy 3 nguồn cùng nộp (React, SEB,
sweeper) không cần phối hợp.

### 4.4. Vì sao `client_attestations` tách khỏi `client_devices`

Hai bảng dễ bị nhầm là một:

| | `client_devices` | `client_attestations` |
|---|---|---|
| Đơn vị | Thiết bị (1 máy) | Phiên thi (1 lần làm bài) |
| Khoá | `(user_id, device_id)` | `(session_id, device_fingerprint)` |
| Tồn tại | Vĩnh viễn tới khi bị thu hồi | Chỉ trong phiên |
| Nội dung | Public key, nhãn, `revoked_at` | Bằng chứng "phiên này đã xác thực" |
| Ai ghi | `client_device_service.register` | `join_exam` khi `is_verified_seb` |

Vì sao cần cả hai: một thiết bị dùng cho nhiều ca thi, và một ca có nhiều thiết bị.
Gộp lại thì không trả lời được câu hỏi "phiên này có thật sự được xác thực không"
sau khi thiết bị bị thu hồi giữa kỳ.

### 4.5. Các cột có thể gây hiểu nhầm

| Cột | Dễ hiểu nhầm là | Thực tế |
|---|---|---|
| `exam_sessions.risk_score` | Điều kiện nộp bài | Chỉ là **metric xếp hạng** cho GV. Nộp bài do ngưỡng `tab_switch + fullscreen_exit` |
| `exam_sessions.device_id` | Khoá ngoại tới `client_devices` | Không có FK. Là chuỗi `sha256(pubkey)[:16]`, có thể NULL (thi bằng web) |
| `exam_sessions.device_fingerprint` | Trùng `device_id` | `device_id` = 16 ký tự, `fingerprint` = 64 ký tự (hash đầy đủ) |
| `exams.max_violation_allowed` | Ngưỡng cuối cùng | Chỉ là **bậc 2**; bậc 1 là `exam_security_configs` |
| `user_agent`, `ip_address` | Dùng để chống gian lận | Chỉ để **phục tra**. Không có logic nào chặn theo IP |
| `questions.difficulty` | Dùng để chia điểm | Chỉ để giảng viên lọc; điểm lấy từ `exam_questions.score` |
| `student_answers.auto_score` | Điểm cuối cùng | Điểm từng câu; tổng nằm ở `exam_sessions.final_score` |
| `violation_logs.client_timestamp` | Mốc thời gian chuẩn | Chỉ để đối chiếu. Mốc chuẩn là `server_timestamp` |

### 4.6. Unique constraint và hệ quả

| Constraint | Hệ quả nghiệp vụ | Xử lý khi vi phạm |
|---|---|---|
| `users.username`, `users.email` | Không trùng tài khoản | `register` trả 400 |
| `exam_schedules.room_code` | Mã phòng là duy nhất toàn hệ thống, không chỉ trong 1 ca | Tạo ca trùng → 400 |
| `exam_sessions (schedule_id, student_id)` | 1 thí sinh chỉ có 1 phiên/ca, F5 không tạo phiên mới | `IntegrityError` → rollback → đọc lại phiên cũ |
| `exam_security_configs.exam_id` | 1 đề chỉ có 1 policy | `save_config` upsert |
| `client_devices (user_id, device_id)` | 1 user không đăng ký trùng cùng thiết bị | `register` trả bản ghi cũ |
| `system_settings.setting_key` | Mỗi khoá cấu hình chỉ 1 giá trị | `set_raw` upsert |

Trường hợp `exam_sessions` đáng chú ý nhất — nếu không xử lý `IntegrityError`, hai
request `join` đồng thời (F5 nhanh, hoặc React StrictMode gọi effect 2 lần) sẽ làm
một request trả 500. Code hiện tại bắt lỗi, rollback, rồi đọc lại phiên đã có.

---

## 5. Các module backend

### 5.1. `app/core/` — hạ tầng

| File | Chức năng |
|---|---|
| `config.py` | `Settings` (pydantic-settings) đọc `.env`. `model_validator` **chặn khởi động** khi `ENV=production` mà `SECRET_KEY` còn default / `DATABASE_URL` là MySQL dev / `CORS_ORIGINS` chứa `*` |
| `database.py` | `engine`, `SessionLocal`, `Base`, dependency `get_db()` |
| `security.py` | `verify_password` / `get_password_hash` (bcrypt), `create_access_token` / `decode_access_token` (JWT HS256), `to_utc_naive` |

### 5.2. `app/models/` — 16 ORM model

Xem [mục 4](#4-mô-hình-dữ-liệu). Toàn bộ DateTime lưu **UTC-naive**, chuẩn hoá qua
`to_utc_naive()` để tránh lệch múi giờ.

### 5.3. `app/schemas/` — Pydantic (hợp đồng dữ liệu)

Điểm đáng chú ý:

- `settings_schema.ExamSecurityConfig` — **schema chuẩn duy nhất** cho cấu hình khoá
  an toàn; dùng cho cả validate khi ghi DB lẫn response cho client.
- `violation_schema.ALLOWED_EVENT_TYPES` + `EVENT_TYPE_SEVERITY` — **server quyết định**
  mức nghiêm trọng, client không gửi severity.
- `question_schema.QuestionPublic` — bản rút gọn khi thi: **không có `is_correct`**.

### 5.4. `app/services/` — nghiệp vụ (trái tim hệ thống)

| Service | Trách nhiệm | Hàm chính |
|---|---|---|
| `auth_service` | Đăng nhập, đăng ký | `authenticate_user`, `register_user` (luôn tạo STUDENT) |
| `question_service` | CRUD câu hỏi, môn học | `get_questions`, `create_question`, `delete_question` |
| `import_service` | Parse `.docx` | `parse_docx`, `parse_table`, `parse_text`, `content_fingerprint` |
| `question_import_service` | Luồng preview → commit | `preview_import`, `commit_import` |
| `exam_service` | CRUD đề + ca thi | `get_exams` (chống N+1), `get_exam_detail`, `create_schedule` |
| `exam_security_service` | **Nguồn sự thật duy nhất** cho policy | `resolve_policy`, `is_safe_browser_required`, `save_config` |
| `exam_session_service` | Vòng đời phiên thi | `join_exam`, `save_answer`, `submit_exam`, `_get_deadline` |
| `grading_service` | Chấm điểm tự động | `grade_session` |
| `anticheat_service` | Ghi vi phạm, risk score, ngưỡng | `record_violation`, `resolve_max_violations_for_exam` |
| `attestation_service` | Challenge-response Ed25519/HMAC | `issue_nonce`, `verify_attestation` |
| `client_device_service` | Đăng ký/thu hồi khoá thiết bị | `register`, `get_active`, `verify_signature` |
| `heartbeat_monitor` | Phát hiện mất kết nối | `scan_stale_connections` |
| `deadline_sweeper` | Tự nộp phiên quá hạn | `sweep_expired_sessions` |
| `report_service` | Thống kê + Excel/PDF | `get_schedule_statistics`, `export_excel`, `export_pdf` |
| `settings_service` | System settings | `get_require_safe_browser_global`, `get_default_security_config` |
| `audit_service` | Nhật ký admin | `log`, `list_logs` |

### 5.5. `app/dependencies/` — FastAPI dependencies

| File | Chức năng |
|---|---|
| `auth.py` | `get_current_user` (giải mã JWT → User), `require_role([...])` (RBAC) |
| `client_identity.py` | Đọc header `X-Client-Type` / `X-Device-Fingerprint` / `X-Attestation-Token`; **chỉ coi là SEB đã xác thực khi token hợp lệ** |
| `exam_time.py` | `check_exam_schedule_active` — chặn thi khi ca chưa mở / đã đóng / bị huỷ |
| `ownership.py` | Kiểm tra quyền sở hữu đề/ca thi/phiên cho TEACHER |

### 5.6. `app/sockets/` — realtime

| File | Chức năng |
|---|---|
| `socket_server.py` | Khởi tạo `AsyncServer`, CORS lấy từ `settings.CORS_ORIGINS` |
| `socket_auth.py` | Xác thực JWT ở handshake; lưu `sid → {user_id, role}` |
| `exam_namespace.py` | Phía thí sinh: `connect`, `join_exam_room`, `heartbeat`, `violation`, `disconnect` |
| `monitor_namespace.py` | Phía giảng viên: `join_monitor_room`, `teacher_force_submit` |

### 5.7. `app/api/routers/` — 8 nhóm endpoint

`auth` · `question` · `exam` · `exam_session` · `report` · `settings` · `security` · `admin`

### 5.8. Một endpoint trông như thế nào

Router **không chứa nghiệp vụ**. Chúng chỉ làm 3 việc: khai báo dependency, gọi
service, trả schema. Ví dụ đầy đủ `POST /exam-sessions/join`:

```python
# backend/app/api/routers/exam_session_router.py:23
@router.post("/join", response_model=ExamTakingStateResponse)
def join_exam(
    data: JoinExamRequest,                                    # ① validate body
    request: Request,                                          # ② IP / UA
    db: Session = Depends(get_db),                             # ③ mở transaction
    identity: ClientIdentity = Depends(get_client_identity),   # ④ đọc header client
    current_user: User = Depends(require_role(["STUDENT", "ADMIN", "TEACHER"])),
):
    return ExamSessionService.join_exam(                       # ⑤ một dòng nghiệp vụ
        db=db,
        room_code=data.room_code,
        student_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        client_identity=identity,
    )
```

Bốn dependency chạy **trước** khi vào hàm, theo thứ tự từ trái sang phải:

| Dependency | Làm gì | Ném lỗi khi |
|---|---|---|
| `JoinExamRequest` | Pydantic validate: `room_code` dài 3–20 | body sai → 422 |
| `get_db` | Mở `SessionLocal()`, đóng ở `finally` | — |
| `get_client_identity` | Giải JWT (gián tiếp qua `get_current_user`), đọc 4 header client, **verify attestation token** | JWT sai → 401 |
| `require_role([...])` | Kiểm `current_user.role.code` | sai role → 403 |

Lợi ích của cách viết này: nếu ai đó quên `require_role` ở một endpoint, nó **lộ ra
ngay** khi đọc danh sách route, vì mỗi route có đúng một dòng `Depends(require_role(...))`.
Đó cũng là cách bản vá phân quyền được áp: thêm dependency vào router, không sửa
từng service.

### 5.9. Luồng phụ thuộc giữa các service

Không có chu trình. Mũi tên = "gọi tới":

```
routers
   │
   ├─▶ auth_service ──────────────▶ core.security
   ├─▶ exam_service ──────────────▶ exam_security_service
   ├─▶ exam_session_service ──────┬▶ exam_security_service
   │                              ├▶ anticheat_service ──▶ settings_service
   │                              ├▶ grading_service
   │                              └▶ dependencies.exam_time
   ├─▶ report_service ────────────▶ (models + openpyxl/reportlab)
   ├─▶ security_router ───────────▶ exam_security_service
   ├─▶ admin_router ──────────────▶ audit_service, settings_service
   └─▶ attestation (qua router) ──▶ attestation_service
                                     └▶ client_device_service

sockets/exam_namespace ──▶ anticheat_service, exam_session_service,
                           exam_security_service
sockets/monitor_namespace ─▶ exam_session_service, anticheat_service
heartbeat_monitor ────────▶ anticheat_service
deadline_sweeper ─────────▶ exam_session_service
```

Vì sao `grading_service` nằm cuối chuỗi: nó chỉ đọc `StudentAnswer` + `QuestionOption`
và ghi `auto_score`. Không service nào gọi ngược lại nó, nên nó không thể tạo chu
trình và có thể test độc lập (thực tế test hiện tại làm đúng vậy).

### 5.10. Nơi nào quyết định "vi phạm"

Đây là câu hỏi hay gây nhầm vì có 4 nơi cùng nhắc tới vi phạm:

| Nơi | Vai trò | Có quyền quyết định? |
|---|---|---|
| `frontend/hooks/*` | Phát hiện sự kiện trong tab | ❌ Không. Chỉ gọi `logViolation` |
| `seb_client/guards/*` | Phát hiện/chặn ở tầng OS | ❌ Không. Chỉ gọi `report` |
| `sockets/exam_namespace.violation` | Nhận, whitelist `event_type` | ❌ Không. Chỉ chuyển tiếp |
| `anticheat_service.record_violation` | Ghi log, tăng đếm, **tính severity, đánh giá ngưỡng** | ✅ **Có** |

Severity do client gửi lên bị **bỏ qua hoàn toàn** — `resolve_severity(event_type)`
tra bảng ở server (`violation_schema.py:25`). Client chỉ được chọn `event_type`
trong `ALLOWED_EVENT_TYPES`; gửi loại lạ bị từ chối kèm log.

Cùng nguyên tắc với điểm số: `grading_service` là nơi duy nhất biết đáp án đúng.

---

## 6. Các module frontend (Lớp A — Web)

### 6.1. Cấu trúc

```
frontend/src/
├── App.jsx                 Định tuyến theo role
├── main.jsx                Entry point
├── components/
│   ├── common/             Alert, Badge, Card, Icon, Input, Modal, Select, Toggle...
│   └── layout/             Layout (sidebar), ProtectedRoute
├── pages/
│   ├── auth/Login.jsx
│   ├── admin/              AdminHome, Settings, Users, AuditLog
│   ├── teacher/            TeacherHome, ExamList, ExamEditor, QuestionBank,
│   │                       ScheduleList, Reports, ImportQuestionsModal
│   ├── monitor/            MonitorDashboard  (realtime)
│   └── exam/               ExamJoin, ExamRoom, ExamResults, PolicyGate
│       └── hooks/          8 hook khoá an toàn
├── services/               apiClient, socketClient, policyService, teacherService
├── store/authStore.js      Zustand
└── utils/labels.js
```

### 6.2. Định tuyến & bảo vệ

| Route | Role | Ghi chú |
|---|---|---|
| `/login` | công khai | |
| `/admin`, `/admin/settings`, `/admin/users`, `/admin/audit-log` | ADMIN | |
| `/teacher`, `/teacher/exams`, `/teacher/exams/:examId`, `/teacher/questions`, `/teacher/schedules`, `/teacher/reports` | TEACHER, ADMIN | |
| `/monitor/:scheduleId` | TEACHER, ADMIN | Ngoài `Layout` (cần toàn màn hình) |
| `/exam/join`, `/exam/results` | STUDENT, ADMIN, TEACHER | |
| `/exam/room` | STUDENT, ADMIN, TEACHER | Ngoài `Layout` — giao diện thi tối giản |

`ProtectedRoute` **chỉ là lớp UX**, không phải bảo mật — mọi endpoint backend tự
kiểm tra JWT + RBAC độc lập.

### 6.3. Tám hook khoá an toàn (`pages/exam/hooks/`)

| Hook | Nhóm | Cơ chế |
|---|---|---|
| `useSecurityPolicy` | Gốc | Cấp `policy` + `logViolation` + socket; **nguồn duy nhất** cho các hook con |
| `useFullscreenLock` | Chặn | Bắt buộc fullscreen khi bắt đầu; phát hiện thoát |
| `useKeyboardBlock` | Chặn | 3 cờ độc lập: copy/paste, DevTools, in |
| `useNavigationLock` | Chặn | Chặn link ra ngoài, Back/Forward, `beforeunload`, `window.open` |
| `useVisibilityMonitor` | Phát hiện | `visibilitychange` + `blur` → TAB_SWITCH |
| `useDevToolsDetector` | Phát hiện | Heuristic `outerWidth − innerWidth` |
| `useViolationWarning` | Cảnh báo | Đếm ngược yêu cầu quay lại (Mức 2, SRS 5.6) |
| `useAutoSave` | Tiện ích | Debounce 1.5s + `flush()` + `beforeunload` keepalive |

**Cách `useSecurityPolicy` sinh ra policy:** đọc từ response `POST /exam-sessions/join`
(`security_policy`, `require_safe_browser`, `restricted_mode`), chuẩn hoá qua
`policyService.normalize()` (gộp với `DEFAULT_SECURITY_CONFIG` để client cũ không vỡ
khi server thêm field mới).

**`handleIncident` trong `ExamRoom.jsx`** gộp mọi sự kiện rời màn thi về một chỗ để
một hành động Alt+Tab (bắn đồng thời `visibilitychange` + `fullscreenchange`) không bị
tính hai lần; có dedupe 1.5s và chặn ở ngưỡng.

### 6.4. Services

| File | Chức năng |
|---|---|
| `apiClient.js` | axios instance: gắn `Authorization: Bearer`, gắn `X-Client-Type: web`, 401 → về `/login`, `extractErrorMessage()` |
| `socketClient.js` | socket.io singleton; `auth: cb => ({token})` đọc token **mới nhất** mỗi lần connect |
| `policyService.js` | Đọc/ghi policy + settings; `normalize()` gộp default |
| `teacherService.js` | Gọi API đề/ca thi/câu hỏi |

### 6.5. State machine của `ExamRoom`

`ExamRoom.jsx` là component lớn nhất frontend (933 dòng) vì nó giữ **8 trạng thái
độc lập** chồng lên nhau. Đọc theo bảng dưới sẽ dễ hơn đọc tuần tự:

| State | Kiểu | Ý nghĩa | Ai đổi |
|---|---|---|---|
| `state` | object \| null | Response của `join` (đề, token, policy, bộ đếm) | `join()` |
| `joining` / `joinError` | bool / string | Đang gọi join / lỗi join | `join()` |
| `gateDismissed` | bool | Thí sinh đã bấm "thi bằng web hạn chế" | click |
| `started` | bool | Đã bấm "Bắt đầu thi" (điều kiện bật guard) | `handleStart()` |
| `answers` | `{qid: {selected_option_ids, fill_blank_text}}` | Đáp án đang làm | chọn đáp án |
| `remaining` | int | Giây còn lại, hiển thị | interval 1s |
| `locked` | bool | Phiên đã bị thu (hết giờ / vượt ngưỡng / nộp thành công) | submit, force_submit |
| `submitting` / `submitError` | bool / string | Đang nộp / lỗi nộp **có thể thử lại** | `submitExam()` |
| `strikes` | `{TAB_SWITCH, FULLSCREEN_EXIT}` | Bộ đếm **hiển thị** (không phải nguồn quyết định) | `handleIncident`, sync từ join |
| `warning` / `warningRemaining` | object / int | Cảnh báo Mức 2 đang đếm ngược | `useViolationWarning` |

`inProgress = Boolean(state) && started && !locked` — **một biểu thức duy nhất**
quyết định toàn bộ 8 hook có chạy hay không. Đây là lý do khi phiên bị thu, mọi
việc chặn lập tức dừng, không cần gỡ từng hook.

**Bốn `ref` không phải là code thừa.** Chúng tồn tại để tránh closure cũ:

| Ref | Vì sao không dùng state trực tiếp |
|---|---|
| `submittingRef` | `setSubmitting` bất đồng bộ; hai sự kiện trong cùng tick đều đọc `false` → nộp 2 lần |
| `submittedRef` | Chặn nộp lặp trong lúc chờ `navigate` |
| `autoSubmitFiredRef` | Đồng hồ tick mỗi giây; phải đảm bảo chỉ tự nộp **một lần** |
| `strikesRef` | `handleIncident` cần đọc bộ đếm **đồng bộ** tại thời điểm gọi (state chưa cập nhật) |

Ngoài ra `flushAnswersRef` và `submitExamRef` giải quyết vấn đề ngược lại: effect
đếm ngược khai báo trước khi `submitExam` tồn tại, nên phải đọc qua ref để luôn
dùng bản mới nhất mà không phải thêm vào deps (thêm vào sẽ tạo lại interval mỗi render).

### 6.6. Vì sao `handleIncident` gộp mọi sự kiện

Một hành động Alt+Tab làm trình duyệt bắn **hai** sự kiện: `visibilitychange`
(vào `useVisibilityMonitor`) và `fullscreenchange` (vào `useFullscreenLock`). Nếu
mỗi hook tự ghi vi phạm, một lần chuyển tab bị tính hai lần.

`handleIncident(type, source)` là điểm gộp duy nhất:

```
handleIncident
  ├─ locked? → bỏ (phiên đã thu, không đếm nữa)
  ├─ < 1.5s từ lần trước? → bỏ (dedupe)
  ├─ đã đủ ngưỡng? → bỏ (UI không vượt số server sẽ áp)
  ├─ logViolation(type)          → socket
  ├─ setStrikes(+1)              → hiển thị
  └─ triggerWarning(type)        → Mức 2
```

Bước "chặn ở ngưỡng" quan trọng: server từ chối ghi khi `status != IN_PROGRESS`, nên
nếu UI vẫn đếm tiếp, thí sinh thấy "23/8" trong khi dashboard đứng ở 8. Chặn ngay
tại client để hai bên khớp nhau.

### 6.7. Điều gì xảy ra khi F5 giữa giờ thi

Đây là kịch bản hay bị bỏ sót nhất:

```
F5
 ├─ React unmount → cleanup của 8 hook chạy (gỡ listener, xoá interval)
 ├─ Khởi tạo lại → ExamRoom gọi join()
 ├─ Backend: phiên ĐÃ TỒN TẠI
 │    ├─ status IN_PROGRESS → giữ nguyên
 │    ├─ status DISCONNECTED → đổi về IN_PROGRESS
 │    ├─ trả saved_answers (đáp án đã lưu khôi phục)
 │    ├─ trả tab_switch_count / fullscreen_exit_count (bộ đếm khôi phục)
 │    └─ KHÔNG tạo phiên mới (unique constraint + nhánh else)
 ├─ `started` về false → hiện lại màn "Sẵn sàng", phải bấm Bắt đầu thi lại
 └─ socket: kết nối mới → join_exam_room
      └─ server thấy socket cũ (nếu chưa kịp disconnect) → DUPLICATE_LOGIN
```

Hai điều dễ hiểu nhầm:

- **Thời gian không dừng.** `remaining_seconds` tính lại từ `started_at` gốc, không
  phải từ lúc F5. Thí sinh mất đúng khoảng thời gian đã trải qua.
- **`fullscreen` phải xin lại.** Trình duyệt yêu cầu user gesture, nên F5 luôn
  thoát fullscreen. Đây là lý do phải có màn "Sẵn sàng" thay vì tự vào lại.

`DUPLICATE_LOGIN` từ F5 nhanh (socket cũ chưa kịp đóng) là **dương tính giả** — nó
cộng 25 risk score oan. Đây là điểm đã biết, ghi ở mục 16.

---

## 7. SEB Client (Lớp B — Desktop)

### 7.1. Kiến trúc

```
seb_client/sebclient/
├── app.py              SebClientApp: Qt chạy TRONG asyncio loop (qasync)
├── __main__.py         Entry point
├── config.py           ClientConfig: backend_url, allowed_origins, key_dir...
├── config_file.py      Đọc file `.seb` (plist) → BrowserPolicy
├── make_seb.py         Công cụ tạo file `.seb` cho giảng viên
├── api/
│   ├── client.py       ApiClient (httpx): login, register_device, join, submit
│   ├── attestation.py  ClientAttestor: 4 bước challenge-response
│   └── heartbeat.py    ExamSocket: socket.io + heartbeat định kỳ
├── guards/             7 guard
├── osint/              Adapter theo OS + keystore
└── ui/
    ├── login_window.py     Đăng nhập + nhập mã phòng
    ├── exam_window.py      Cửa sổ thi (QWebEngineView) — chế độ có backend
    ├── policy_browser_window.py  Cửa sổ khoá theo file `.seb` — chế độ không backend
    ├── web_page.py         GuardedWebEnginePage (chặn action)
    ├── warning_overlay.py  Cảnh báo đếm ngược
    └── blocked_overlay.py  Màn hình chặn
```

**Hai chế độ chạy:** (a) mở không đối số → chế độ thi có backend (login + join
+ socket); (b) mở kèm đường dẫn file `.seb` → chế độ trình duyệt khoá theo cấu
hình, không backend, không giám sát. `_config_file_from_argv()` trong `app.py`
quyết định chế độ **trước khi** validate `.env`, vì chế độ (b) không dùng backend.

| | Chế độ thi | Chế độ `.seb` |
|---|---|---|
| Trang mở | `SEB_EXAM_URL_TEMPLATE` | `startURL` trong file |
| Khoá an toàn | policy server trả về | khoá trong file `.seb` |
| Heartbeat / vi phạm | có, ghi dashboard | không, chỉ ghi log |
| Tự nộp khi hết giờ | có | không (file không chứa thời lượng) |

**Vì sao `qasync`:** mọi việc mạng (HTTP, socket) là async. Dùng `app.exec()` thông
thường thì coroutine không bao giờ chạy và cửa sổ đứng hình mỗi nhịp heartbeat.
Chế độ `.seb` không có việc mạng nên chạy `app.exec()` thường — đơn giản hơn,
và lỗi Qt không bị che bởi tầng event loop của asyncio.


### 7.2. Bảy guard

| Guard | Cơ chế | Sự kiện báo |
|---|---|---|
| `KioskGuard` | Fullscreen + ẩn taskbar/dock + chặn đóng cửa sổ | `RIGHT_CLICK_ATTEMPT` |
| `KeyboardGuard` | `eventFilter` chặn tổ hợp phím | `COPY_PASTE_ATTEMPT` / `DEVTOOLS_DETECTED` |
| `DevToolsGuard` | Chặn phím mở DevTools + kiểm tra định kỳ | `DEVTOOLS_DETECTED` |
| `ClipboardGuard` | Xoá clipboard định kỳ (Windows: tầng OS) | `COPY_PASTE_ATTEMPT` |
| `DownloadGuard` | Chặn tải file | `COPY_PASTE_ATTEMPT` |
| `NavigationGuard` | Chặn điều hướng ra ngoài `allowed_origins` | `UNAUTHORIZED_CLIENT` |
| `SessionGuard` | Đếm ngược hết giờ + poll chuyển cửa sổ mỗi giây | `TAB_SWITCH` (qua OS) |

`BaseGuard` có **dedupe 1500ms** để Alt+Tab liên tục không làm đầy bảng vi phạm.

### 7.3. OS Adapter (`osint/`)

| Adapter | Cơ chế mạnh | Phụ thuộc |
|---|---|---|
| `WindowsAdapter` | `RegisterHotKey` chặn Alt+Tab toàn cục, ẩn `Shell_TrayWnd`, `OpenClipboard/EmptyClipboard`, phát hiện foreground PID | `ctypes` (stdlib); `pywin32` tuỳ chọn cho máy in |
| `MacOSAdapter` | `CGEventTap`, `NSApplication`, `NSPasteboard` | Cần quyền Accessibility |
| `LinuxAdapter` | `_NET_ACTIVE_WINDOW` (X11) | `python-xlib`; Wayland **không hỗ trợ** monitor_switch |
| `UnsupportedAdapter` | Trả `False` mọi thứ, không nổ | — |

`capability_matrix.CAPABILITIES` khai báo cơ chế từng nền tảng; phần thiếu được gửi
lên server trong `unsupported` để giảng viên nhìn thấy máy nào bảo vệ chưa đủ.

### 7.4. Attestation (chống giả mạo client)

```
1. POST /api/auth/client-devices   → server lưu PUBLIC KEY, trả device_id
2. POST /api/auth/client-nonce     → nonce dùng 1 lần, TTL 30s
3. Client ký: message = "nonce|client_version|device_fingerprint|device_id"
              signature = Ed25519(private_key, message)
4. POST /api/auth/client-attest    → server verify bằng public_key
                                     → cấp attestation_token (5 phút)
```

Vì server **chỉ giữ public key**, về mặt toán học nó không thể tự ký thay client.
`device_id = sha256(public_key)[:16]` — ổn định, không dùng MAC/hostname (người dùng
sửa được).

Đường HMAC cũ (`device_secret` dẫn xuất từ `SECRET_KEY`) vẫn giữ để client cũ không
bị chặn đột ngột; sẽ gỡ khi đủ client dùng Ed25519.

### 7.5. Chế độ mở bằng file cấu hình `.seb`

Đây là mô hình của SEB chính thức: giảng viên phát hành **một file plist XML**,
thí sinh double-click file đó, client khởi động thành trình duyệt khoá đúng theo
cấu hình trong file. Không login, không join phòng, không socket.

**Luồng quyết định chế độ** (`app.py:main`):

```python
config_file = _config_file_from_argv(sys.argv)     # quét argv tìm *.seb / *.seb2
if config_file:
    _log_capabilities()
    return _run_config_file_mode(config_file, log_file)   # → app.exec() thường
# ngược lại: chế độ thi có backend → qasync.QEventLoop
```

Chế độ này được nhận diện **trước** `config.validate()`, nên một `.env` thiếu
khoá không chặn việc mở file cấu hình.

**Đọc file** (`config_file.load_config_file` → `parse_config`):

| Khoá plist | → `BrowserPolicy` | Ghi chú |
|---|---|---|
| `startURL` (hoặc `startUrl`) | `start_url` | Bắt buộc; sai/thiếu → `ConfigFileError` |
| `allowPrint` | `allow_print` | |
| `clipboardPolicy` | `allow_copy_paste` | `1` = chặn; `0`/`2` = cho phép; giá trị lạ → chặn |
| `enableRightMouse` | `allow_right_mouse` | |
| `allowDeveloperConsole` | `allow_devtools` | |
| `browserWindowAllowAddressBar` | `allow_address_bar` | |
| `browserWindowAllowReload` | `allow_reload` | `false` → `NavigationGuard` không reload |
| `enableAltTab` | `block_alt_tab` (đảo) | |
| `enableEsc`, `enableCtrlEsc`, `enablePrintScreen` | `block_*` (đảo) | |
| `blockPopUpWindows` | `block_popups` | |
| `allowQuit` + `hashedQuitPassword` | `allow_quit`, `requires_quit_password` | |
| `whitelistURLFilter`, `URLFilterRules` | `allowed_origins` | Chỉ nhận rule có `expression` dạng URL đầy đủ |

`startURL` phải là `http://`/`https://` — `file://` bị từ chối (mở file cục bộ
trong cửa sổ "khoá" là bề mặt tấn công, không phải tính năng).

**Không im lặng bỏ qua khoá chưa hỗ trợ.** `_collect_unsupported()` liệt kê các
khoá mà việc bỏ qua sẽ khiến giảng viên hiểu sai mức bảo vệ — `enableURLFilter`,
`killExplorerShell`, `createNewDesktop`, `monitorProcesses`, `browserExamKey`,
`sebServerURL`, `embeddedCertificates`, `proxySettingsPolicy`… Danh sách này hiện
trong hộp thoại khi mở file **và** ghi log. (File `.seb` thật có >200 khoá; chỉ
những khoá ảnh hưởng đến nhận thức về an toàn mới được báo.)

**`PolicyBrowserWindow`** dựng đúng bộ guard như `ExamWindow` nhưng:
- bỏ `SessionGuard` (không có deadline, không heartbeat),
- bỏ hẳn guard mà policy cho phép (`allow_devtools` → không cài `DevToolsGuard`;
  `allow_copy_paste` → không cài `ClipboardGuard`),
- truyền `policy` vào `KeyboardGuard`, `KioskGuard`, `GuardedWebEnginePage` để
  từng cơ chế tự nới lỏng thay vì chạy rồi bỏ kết quả,
- `_log_violation` chỉ ghi log — không có server để gửi.

**Giới hạn của chế độ này** (phải nói rõ với giảng viên): không giám sát, không
đếm vi phạm, không tự nộp khi hết giờ, `hashedQuitPassword` mới chỉ được đọc chứ
chưa có hộp thoại nhập mật khẩu giám thị.

**Công cụ tạo file:** `python -m sebclient.make_seb --url ... --out exam.seb`
(`--allow-print`, `--allow-copy`, `--allow-devtools`, `--allow-alt-tab`,
`--allow-origin`, `--lock-quit`…). Hướng dẫn đầy đủ:
`seb_client/packaging/HUONG_DAN_FILE_CAU_HINH.md`.

### 7.6. Vì sao webview cần `ClientIdentityInterceptor`

Khi trang web thi chạy trong `QWebEngineView`, request của nó **không** đi qua
`ApiClient` (httpx) của Python — nó do Chromium phát ra. Nghĩa là mặc định request
đó **không có** `X-Client-Type`, `X-Attestation-Token`, `X-Device-Fingerprint`.

Hậu quả (đã kiểm chứng bằng probe với backend thật):

```
1) SEB client join  -> restricted_mode = False     ← đúng
2) webview join     -> restricted_mode = True      ← SAI
   session.attestation_status = VERIFIED, client_type = seb
3) => PolicyGate hiện khi đã ở trong SEB? True
```

Thí sinh đang dùng đúng SEB vẫn thấy màn hình "Đề thi này yêu cầu Safe Exam
Browser", và mỗi lần join cộng oan +20 risk score (`UNAUTHORIZED_CLIENT`).

Cách vá: `ui/request_interceptor.py`

```
QWebEngineProfile
   └── ClientIdentityInterceptor (QWebEngineUrlRequestInterceptor)
          interceptRequest(info):
            ├─ origin của request ∈ allowed_origins?
            │    ├─ không → bỏ qua (KHÔNG gắn gì)
            │    └─ có    → header_provider() → info.setHttpHeader(...)
            └─ header_provider đọc token HIỆN TẠI mỗi lần gọi
```

Ba quyết định thiết kế:

1. **Chỉ gắn cho origin trong allow-list.** Attestation token là credential; gắn
   kèm khi webview tải ảnh/CDN bên thứ ba là rò rỉ token ra ngoài. So khớp theo
   `scheme://host:port` đã chuẩn hoá, không so tiền tố chuỗi (nếu không
   `localhost:5173.evil.com` sẽ lọt).
2. **Đọc header mỗi request, không cache.** Attestation token sống 5 phút; giữ giá
   trị cũ nghĩa là sau phút thứ 5 mọi request bị từ chối.
3. **Không bao giờ ném lỗi.** Hàm chạy trong vòng lặp mạng của Chromium; một
   exception ở đây có thể chặn request và làm trắng trang.

Header do interceptor đặt **ghi đè** header do JS tự set. Đã kiểm chứng: axios
trong trang gửi `X-Client-Type: web`, server vẫn nhận `seb`.

**Attestation phải làm mới trong phiên dài.** Token TTL 5 phút, ca thi 45–120 phút.
`ExamWindow._start_attestation_refresh()` chạy `QTimer` mỗi 240s để attest lại;
không có bước này thì sau phút thứ 5, F5 giữa giờ sẽ đẩy thí sinh về `restricted_mode`.

### 7.7. Chi tiết từng guard — chặn được gì, không chặn được gì

Bảng dưới nêu **giới hạn thật**, không chỉ mô tả tính năng:

| Guard | Cơ chế thật | Chặn được | **Không** chặn được |
|---|---|---|---|
| `KioskGuard` | `showFullScreen()` + `enter_kiosk()` (OS) + event filter | Đóng cửa sổ, chuột phải, thoát fullscreen (phát hiện) | Alt+Tab nếu OS adapter thiếu; phím Windows |
| `KeyboardGuard` | `QShortcut` (`ApplicationShortcut`) + `eventFilter` trên `web_view` | Ctrl+C/V/X/A/P/S/U, F12, Ctrl+Shift+I/J/C | Tổ hợp do OS xử lý trước (Alt+Tab ở một số WM); macro bên ngoài |
| `DevToolsGuard` | Tắt `JavascriptCanPaste`, `ScreenCaptureEnabled`; quét cửa sổ con mỗi 1s | DevTools mở dạng docked trong cùng cửa sổ | DevTools mở cửa sổ rời; Chromium remote debugging từ ngoài |
| `ClipboardGuard` | Xoá clipboard mỗi 2s (OS nếu có) | Nội dung đã nằm trong clipboard | Chụp màn hình; ghi chú giấy; clipboard trong < 2s |
| `DownloadGuard` | `QWebEngineProfile.downloadRequested` → `item.cancel()` | Tải file qua Chromium | Lưu trang bằng phím tắt OS; in ra PDF nếu PrintScreen không bị chặn |
| `NavigationGuard` | `urlChanged` → so origin → `reload_exam()` | Điều hướng ra ngoài `allowed_origins` | Gõ JavaScript trong DevTools (đã bị chặn ở lớp khác) |
| `SessionGuard` | `QTimer` 1s: đếm ngược + `poll_window_switch()` | Không chặn gì — chỉ **phát hiện** hết giờ và chuyển cửa sổ | Tất cả hành vi thật |

Điểm quan trọng: **không guard nào tự phạt.** Tất cả chỉ gọi `report()` → socket →
server quyết định. `BaseGuard.report()` có dedupe 1500ms theo `event_type` để
Alt+Tab liên tục không làm đầy bảng vi phạm.

`eventFilter` gắn vào **`web_view`**, không gắn vào `QApplication` — đã kiểm chứng
thực nghiệm rằng gắn vào `QApplication` làm **segfault** `QWebEngineView` ngay khi
trang bắt đầu render.

### 7.8. Vòng đời một cửa sổ thi

```
SebClientApp.start()
  └─ LoginWindow.show()
       └─ [đăng nhập OK] → signal login_succeeded
            └─ ExamWindow(...)            ← tạo
                 ├─ _build_view()          profile tạm + page + interceptor
                 ├─ _build_os_adapter()    một adapter duy nhất cho cả app
                 ├─ _build_guards()        7 guard, CHƯA install
                 └─ show()
            └─ asyncio.ensure_future(window.start_exam())
                 ├─ _attest()              Ed25519, lấy attestation_token
                 ├─ api.join_exam()        tạo/khôi phục phiên
                 ├─ _session_guard.set_deadline(remaining_seconds)
                 ├─ ExamSocket.connect_and_join()
                 ├─ guard.install()  ×7     ← từ đây mới thật sự chặn
                 ├─ load_exam_page()        webview nạp URL có &embedded=1
                 └─ _start_attestation_refresh()   QTimer 240s
```

Điều đáng chú ý: guard **chưa** install trong lúc đang login/attest/join. Nếu
install sớm, việc giám thị thao tác trên máy trong lúc chờ mạng sẽ bị ghi vi phạm oan.

Chiều đóng (thứ tự **bắt buộc**):

```
closeEvent
  ├─ stop attestation timer
  ├─ guard.uninstall() ×7          gỡ listener trước
  ├─ socket.close_best_effort()    không await trong closeEvent
  ├─ _kiosk_guard._allow_close = True
  └─ _release_webengine()          shiboken6.delete(view, page)
```

`_release_webengine()` phải chạy trước khi `QApplication` bị phá huỷ; nếu không,
`QWidget::~QWidget → QWindow::close` sẽ segfault trong `runCleanupFunctions`. Đây
là lỗi vòng đời Qt WebEngine, không phải lỗi logic, và không thể "sửa" bằng try/except.

---

## 8. Socket.IO — giao thức thời gian thực

### 8.1. Vì sao dùng Socket.IO (không phải REST polling)

- Cần **đẩy** sự kiện ngay khi xảy ra (< 1s): vi phạm, cưỡng chế thu bài.
- Cần **nhịp sống** để phát hiện mất kết nối: heartbeat 10s.
- Socket.IO có sẵn reconnection, room, ack — không phải tự viết trên WebSocket thuần.

### 8.2. Xác thực (bắt buộc từ handshake)

```
Client                              Server (socket_auth.py)
  │  connect(auth={token: JWT})  ──▶  decode_access_token()
  │                                    ├─ sai/thiếu → raise ConnectionRefusedError
  │                                    └─ đúng → lưu sid→{user_id, role}
  │  ◀── connected
```

Token được đọc theo thứ tự: `auth` dict → query `?token=` (dự phòng reconnect) →
header `Authorization`. Attestation token (`typ` có giá trị) **bị từ chối** — chỉ
chấp nhận access token đăng nhập.

`cors_allowed_origins` lấy từ `settings.CORS_ORIGINS`, không còn `"*"`.

### 8.3. Sự kiện — chiều thí sinh

| Client emit | Server xử lý | Server emit lại |
|---|---|---|
| `join_exam_room {room_code, session_token}` | Kiểm tra phiên tồn tại, **chủ sở hữu**, phát hiện đăng nhập trùng (kick socket cũ + log `DUPLICATE_LOGIN`) | `student_status_change` → phòng monitor |
| `heartbeat {}` | Cập nhật `last_heartbeat` | ack `{status:"alive", server_time}` |
| `violation {type, detail, clientTimestamp}` | Whitelist `event_type`, **server tự quyết severity**, ghi log, đánh giá ngưỡng | `violation_alert` → monitor; nếu vượt ngưỡng: `force_submit` cho thí sinh + `student_force_submitted` cho monitor |
| (disconnect) | Gỡ khỏi `active_sockets` | `student_status_change` |

### 8.4. Sự kiện — chiều giảng viên

| Client emit | Server xử lý |
|---|---|
| `join_monitor_room {room_code}` | Yêu cầu role ADMIN/TEACHER; vào room `monitor_<CODE>`; trả danh sách thí sinh đang kết nối + ngưỡng vi phạm |
| `teacher_force_submit {session_id, reason}` | Yêu cầu role ADMIN/TEACHER; gọi `submit_exam(..., skip_auth_check=True)`; emit `force_submit` cho thí sinh + broadcast monitor |

### 8.5. Room

- `room_<ROOM_CODE>` — socket của thí sinh tự vào khi `join_exam_room` (cho phép
  broadcast tới toàn bộ thí sinh của một ca nếu cần).
- `monitor_<ROOM_CODE>` — giảng viên theo dõi một ca.
- Ngoài room, `active_sockets[sid]` giữ `{session_token, session_id, room_code,
  student_id, student_name, student_code, last_heartbeat}` — đây là nguồn để
  heartbeat monitor và giám sát đọc trạng thái từng thí sinh.

### 8.6. Giới hạn đã biết

`active_sockets` và `_pending_nonces` là **in-memory**. Chạy multi-worker (uvicorn
`--workers N`) sẽ mỗi worker chỉ thấy socket/nonce của riêng mình. Muốn scale phải
chuyển sang Redis. Đây là lựa chọn có chủ đích cho đồ án chạy 1 tiến trình, và được
ghi rõ trong code.

### 8.7. Bảng sự kiện đầy đủ (đối chiếu code)

Hai chiều, ba phòng. Cột "ai nhận" quan trọng hơn cột "tên sự kiện" khi debug.

| Sự kiện | Chiều | Ai emit | Ai nhận | Payload |
|---|---|---|---|---|
| `connect` | handshake | client | server | `auth={token}` → JWT bắt buộc |
| `join_exam_room` | C→S | thí sinh | server | `{room_code, session_token}` |
| `heartbeat` | C→S | thí sinh | server | `{}` |
| `violation` | C→S | thí sinh | server | `{type, detail, clientTimestamp}` |
| `join_monitor_room` | C→S | GV | server | `{room_code}` |
| `teacher_force_submit` | C→S | GV | server | `{session_id, reason}` |
| `student_status_change` | S→C | server | `monitor_<CODE>` | `{session_id, status, ...}` |
| `violation_alert` | S→C | server | `monitor_<CODE>` | `{event_type, severity, risk_score, ...}` |
| `student_force_submitted` | S→C | server | `monitor_<CODE>` | `{session_id, reason, max_violations}` |
| `force_submit` | S→C | server | **1 sid** hoặc `room_<CODE>` | `{reason}` |
| `disconnect` | lifecycle | client/server | server | — |

Ba điểm cần nhớ:

1. **`force_submit` gửi tới một `sid` cụ thể** khi vượt ngưỡng (`to=sid`), nhưng
   gửi tới **`room_<CODE>`** khi giám thị thu bài cả phòng. Cùng tên, khác phạm vi.
2. **`heartbeat` trả ack** `{status:"alive", server_time}`. Client hiện không dùng
   `server_time` này (đã lấy ở `join`), nhưng nó có sẵn nếu cần đồng bộ lại.
3. **Không có sự kiện nào để client yêu cầu "cho tôi xem đáp án đúng."** Đáp án
   không bao giờ rời server trong lúc thi.

### 8.8. Vì sao `embedded=1` phải có

Nếu trang web trong webview tự mở socket, server thấy **2 kết nối cho cùng
`session_id`**:

```
socket A (SEB Client)  ── join_exam_room ──▶  active_sockets[A]
socket B (trang web)   ── join_exam_room ──▶  thấy A cùng session_id
                                              ├─ ghi DUPLICATE_LOGIN (+25 risk)
                                              ├─ emit force_submit → A
                                              └─ pop A khỏi active_sockets
```

Kết quả: dùng đúng SEB Client lại bị **buộc nộp bài**. Đây là lý do
`useSecurityPolicy.js:47` có `if (embeddedInSeb) return undefined`, và lý do
`SEB_EXAM_URL_TEMPLATE` bắt buộc chứa `&embedded=1`.

Hệ quả kéo theo: khi `embedded=1`, `logViolation` cũng không gửi gì (vì
`socketRef.current` là null). Đúng ý đồ — SEB Client đã chặn ở tầng OS và tự gửi
sự kiện mạnh hơn; nếu web cũng gửi thì một hành vi bị đếm hai lần.

### 8.9. Trình tự handshake chi tiết

```
1. Client:  io(url, {auth: cb => cb({token})})
2. Server:  connect(sid, environ, auth)        exam_namespace.py:29
            ├─ authenticate_socket(sid, auth, environ)   socket_auth.py:49
            │    ├─ _extract_token: auth.token → query ?token= → header Bearer
            │    ├─ decode_access_token(token)   → payload
            │    ├─ payload["typ"] tồn tại?      → từ chối (đó là attestation token)
            │    ├─ user_id = int(payload["sub"])
            │    └─ _identities[sid] = {user_id, role}
            └─ None → raise ConnectionRefusedError → client nhận "connect_error"
3. Client:  emit("join_exam_room", {room_code, session_token})
4. Server:  ├─ identity_of(sid) có?                    → không: Unauthorized
            ├─ session tồn tại & chưa SUBMITTED?
            ├─ STUDENT chỉ được join phiên của mình
            ├─ có socket khác cùng session_id?          → DUPLICATE_LOGIN, kick
            ├─ sio.enter_room(sid, f"room_{CODE}")
            ├─ active_sockets[sid] = {...}
            └─ emit student_status_change → monitor_<CODE>
5. Từ đây: heartbeat mỗi 10s cập nhật last_heartbeat
```

Điểm bảo mật then chốt ở bước 4: trước bản vá, chỉ cần biết `session_token` của
bạn cùng phòng là gắn được socket và gửi vi phạm thay người đó. Nay phải là chủ
phiên, hoặc ADMIN/TEACHER.

---

## 9. Logic nghiệp vụ cốt lõi

### 9.1. Thứ tự ưu tiên cấu hình khoá an toàn

`ExamSecurityService.resolve_policy(db, exam_id)`:

```
1. exam_security_configs (cấu hình riêng của đề)
2. system_settings["default_security_config"] (mặc định hệ thống)
   └─ nếu DB hỏng/không có → ExamSecurityConfig() (giá trị mặc định code)
```

`is_safe_browser_required(exam)` = `exam.require_safe_browser AND global_toggle`
— **AND**, nên giảng viên tắt được cho từng đề dù hệ thống đang bật.

### 9.2. Ngưỡng vi phạm (3 bậc)

`AnticheatService.resolve_max_violations_for_exam`:

```
1. exam_security_configs → max_tab_switch + max_fullscreen_exit
2. exams.max_violation_allowed
3. settings.DEFAULT_MAX_VIOLATION_ALLOWED (5)
```

**Chỉ đếm `tab_switch_count + fullscreen_exit_count`** vào ngưỡng. Các loại khác
(`DEVTOOLS_DETECTED`, `COPY_PASTE_ATTEMPT`, `RIGHT_CLICK_ATTEMPT`, `CONNECTION_LOST`,
`DUPLICATE_LOGIN`, `UNAUTHORIZED_CLIENT`) **vẫn ghi log và cộng risk_score** nhưng
không ăn vào quota chuyển tab — tránh tự nộp oan và tránh UI lệch server.

`risk_score` là **metric hiển thị cho GV**, không phải điều kiện nộp bài.

### 9.3. Trọng số risk score

| Sự kiện | Điểm | Severity |
|---|---|---|
| `TAB_SWITCH` | 10 | LOW |
| `FULLSCREEN_EXIT` | 15 | MEDIUM |
| `DEVTOOLS_DETECTED` | 30 | HIGH |
| `COPY_PASTE_ATTEMPT` | 5 | MEDIUM |
| `RIGHT_CLICK_ATTEMPT` | 5 | MEDIUM |
| `DUPLICATE_LOGIN` | 25 | HIGH |
| `CONNECTION_LOST` | 5 | MEDIUM |
| `UNAUTHORIZED_CLIENT` | 20 | HIGH |

Trần `MAX_RISK_SCORE = 1000`.

### 9.4. Đồng hồ thi — server quyết định

`_get_deadline(session, schedule)`:

```
deadline = min(started_at + exam.duration_minutes, schedule.end_time)
```

- `POST /join`: nếu `remaining_seconds <= 0` → tự nộp `AUTO_TIMEOUT` rồi trả 400.
- `POST /save-answer`: `now > deadline` → 403 "Đã hết thời gian làm bài".
- Client chỉ **hiển thị** đếm ngược; không được quyết định.

### 9.5. Chấm điểm (`GradingService.grade_session`)

Điểm mỗi câu lấy từ `exam_questions.score` (không phải `questions`).

| Loại câu | Cách tính |
|---|---|
| `SINGLE_CHOICE` | Đúng 1 đáp án và nằm trong tập đúng → full điểm |
| `MULTI_CHOICE` | `ratio = (TP − FP) / |correct|`; nếu `FP ≥ TP` → 0; điểm = `score × ratio` (làm tròn 2 chữ số) |
| `FILL_BLANK` | So khớp text đã `strip().lower()` với các đáp án đúng |

Quy tắc `FP ≥ TP → 0` chống chọn bừa toàn bộ (chọn hết sẽ ra điểm 0, không phải điểm
một phần).

**Ví dụ số — câu MULTI_CHOICE 2 điểm, 4 đáp án đúng là {A, B, C, D}:**

| Thí sinh chọn | TP | FP | ratio | Điểm |
|---|---|---|---|---|
| A, B | 2 | 0 | 2/4 = 0.5 | 1.00 |
| A, B, C | 3 | 0 | 3/4 = 0.75 | 1.50 |
| A, B, C, D | 4 | 0 | 4/4 = 1.0 | 2.00 |
| A, E | 1 | 1 | FP ≥ TP → 0 | 0.00 |
| A, B, E | 2 | 1 | 1/4 = 0.25 | 0.50 |
| E, F, G | 0 | 3 | FP ≥ TP → 0 | 0.00 |
| (không chọn) | 0 | 0 | 0/4 = 0 | 0.00 |

Điểm âm **không** xảy ra: `ratio = max(0.0, ...)`. Thí sinh không bao giờ bị trừ
điểm câu khác vì một câu sai.

**Ba điều cần biết về cách chấm:**

1. Chấm **ngay khi nộp**, không có bước duyệt lại. `submit_exam` gọi
   `grade_session` trong cùng transaction.
2. `manual_score` tồn tại trong schema nhưng **chưa có UI/logic** dùng. Điểm hiện
   tại hoàn toàn tự động.
3. Câu `FILL_BLANK` so khớp **chính xác sau khi chuẩn hoá** — không có fuzzy match,
   không bỏ dấu tiếng Việt. Nhiều đáp án đúng được khai bằng nhiều `QuestionOption`
   có `is_correct=True`.

### 9.5.1. Vì sao công thức MULTI_CHOICE không dùng "trừ điểm tuyệt đối"

Công thức `(TP − FP) / |correct|` có một tính chất quan trọng: **chọn hết mọi đáp
án luôn được 0 điểm** (vì `FP = số đáp án sai`, `TP = số đáp án đúng`; nếu đề có
nhiều đáp án sai hơn đúng thì `FP > TP` → 0; nếu bằng thì `FP ≥ TP` → 0).

Nếu dùng `TP / (TP + FP + FN)` kiểu F1, thí sinh chọn hết sẽ được điểm cao — sai
hoàn toàn về mặt khuyến khích hành vi. Đây là lý do công thức hiện tại được chọn,
và có test khoá lại hành vi này.

### 9.6. Vào phòng thi (`join_exam`)

```
room_code → ExamSchedule
  ├─ không có                          → 404
  ├─ check_exam_schedule_active()      → 400 (chưa mở / đã đóng / bị huỷ)
  └─ exam                              → 500 nếu ca thiếu đề

policy = resolve_policy(exam)
seb_required = is_safe_browser_required(exam)

client khai SEB? → phải có attestation token hợp lệ mới tin
is_verified_seb = claims_seb AND attested
restricted_mode = seb_required AND NOT is_verified_seb

session đã tồn tại?
  ├─ SUBMITTED → 400 "đã nộp"
  └─ có rồi   → cập nhật IP/UA/client; DISCONNECTED→IN_PROGRESS; CHỈ NÂNG attestation
                (join lại không xoá dấu vết SEB đã xác thực)
  └─ chưa có  → tạo ExamSession(IN_PROGRESS, session_token=sess_<uuid4>)
                race → IntegrityError → rollback, đọc lại session

restricted_mode → ghi violation UNAUTHORIZED_CLIENT (bằng chứng, không chặn)
remaining <= 0  → tự nộp AUTO_TIMEOUT + 400
trả ExamTakingStateResponse (questions KHÔNG có is_correct,
     + security_policy, require_safe_browser, restricted_mode,
     + tab_switch_count, fullscreen_exit_count, saved_answers)
```

### 9.7. Lưu đáp án (`save_answer`)

Kiểm tra theo thứ tự:
1. Phiên tồn tại và chưa `SUBMITTED`.
2. Chủ sở hữu (STUDENT chỉ lưu phiên mình).
3. Ca có đề.
4. **Chưa quá deadline** (server-side).
5. `question_id` **thuộc đề này**.
6. `selected_option_ids` **thuộc câu hỏi này**.
7. Upsert `student_answers`.

### 9.8. Nộp bài (`submit_exam`)

```
chuẩn hoá submit_type (không hợp lệ → MANUAL)
kiểm tra chủ sở hữu (STUDENT chỉ nộp phiên mình; hệ thống/giáo viên bỏ qua)
nếu chưa SUBMITTED:
    status = SUBMITTED, submitted_at, submit_type
    → grade_session() ngay
trả ExamResultResponse (điểm, risk_score, bộ đếm vi phạm)
```

Idempotent: nộp lại phiên đã `SUBMITTED` trả kết quả cũ.

### 9.9. Import câu hỏi từ `.docx`

```
preview_import(file, subject_id)
  ├─ kiểm tra .docx + ≤ 5MB
  ├─ parse_docx(): tự nhận diện BẢNG Word hay VĂN BẢN phân tách
  ├─ content_fingerprint() chuẩn hoá (bỏ hoa/thường, dấu câu, khoảng trắng)
  ├─ lọc trùng TRONG CÙNG subject_id
  └─ lưu token + danh sách câu (TTL 30 phút), KHÔNG ghi DB

commit_import(token, subject_id)
  ├─ kiểm tra trùng lại (GV có thể mở 2 cửa sổ)
  ├─ ghi Question + QuestionOption
  └─ xoá token (chống import 2 lần)
```

Tách preview/commit để giảng viên duyệt trước khi ghi thật.

---

## 10. Cơ chế bảo mật nhiều lớp

### 10.1. Xác thực & phân quyền

| Lớp | Cơ chế |
|---|---|
| Mật khẩu | bcrypt (truncate 72 byte theo chuẩn bcrypt) |
| Phiên | JWT HS256, TTL 480 phút, chứa `sub`, `role`, `exp` |
| RBAC | `require_role([...])` ở mọi endpoint ghi |
| Sở hữu | `ownership.py`: TEACHER chỉ thao tác đề mình tạo / ca mình phụ trách |
| Socket | JWT bắt buộc ở handshake + kiểm tra role cho sự kiện giám thị |
| Thiết bị | Ed25519 challenge-response, thu hồi được, chỉ ADMIN mở khoá |
| Production | `ENV=production` chặn secret mặc định / DB không mật khẩu / CORS `*` |

### 10.2. Bảo vệ dữ liệu khi thi

- `QuestionPublic` **không chứa `is_correct`** — đáp án nằm hoàn toàn ở server.
- `save_answer` kiểm tra `question_id` và `option_id` thuộc đề/câu hiện tại — chặn
  dựng bài giả bằng ID tuỳ ý.
- Shuffle đề/câu hỏi theo seed `session_token` → mỗi thí sinh một thứ tự **ổn định
  riêng** (không đổi khi F5, không giống người khác).

### 10.3. Chống gian lận

| Tầng | Cơ chế | Ghi nhận |
|---|---|---|
| Trình duyệt | fullscreen, chặn copy/paste, chặn/phát hiện DevTools, giám sát tab, khoá điều hướng, chặn in | qua socket `violation` |
| Desktop | kiosk, keyboard, devtools, clipboard, download, navigation | qua guard → socket |
| Hệ điều hành | Alt+Tab hotkey, ẩn taskbar, xoá clipboard, foreground PID | qua OS adapter |
| Server | đếm ngưỡng, tự nộp, heartbeat timeout, phát hiện đăng nhập trùng | DB + emit monitor |

### 10.4. Cảnh báo 2 mức (SRS 5.6)

- **Mức 1** (im lặng): ghi log vi phạm, cộng risk score.
- **Mức 2**: `useViolationWarning` hiện đếm ngược `warn_countdown_seconds` yêu cầu
  quay lại. Đây **chỉ là thông báo**, không phải điều kiện tính vi phạm.

---

## 11. Các tiến trình nền

Khởi động trong `main.py` (`startup`), huỷ trong `shutdown`:

| Task | Chu kỳ | Việc làm |
|---|---|---|
| `start_heartbeat_monitor` | 10s | Quét `active_sockets`; im lặng > 30s → ghi `CONNECTION_LOST` **trước**, rồi đặt `DISCONNECTED`, rồi emit monitor |
| `start_deadline_sweeper` | 30s | Quét phiên `IN_PROGRESS`/`DISCONNECTED`; quá `deadline + 15s` → tự nộp `AUTO_TIMEOUT` |

Thứ tự ghi `CONNECTION_LOST` trước khi đổi trạng thái là **có chủ đích**:
`record_violation` chỉ ghi cho phiên `IN_PROGRESS`; đổi trạng thái trước sẽ làm mất
bằng chứng phục tra.

Sweeper trễ 15s để nhường client tự nộp trước (client thắng cuộc đua trong trường hợp
bình thường; sweeper là lưới an toàn cho trường hợp tab bị đóng / tắt máy).

### 11.1. Ai nộp bài khi hết giờ — cuộc đua 3 bên

Hết giờ là lúc có **3 cơ chế** cùng muốn nộp. Chúng không phối hợp với nhau, chỉ
dựa vào tính idempotent của `submit_exam`:

| Thứ tự | Cơ chế | Thời điểm | Điều kiện |
|---|---|---|---|
| 1 | React `ExamRoom` | `remaining === 0` | Trang web còn mở và JS còn chạy |
| 2 | SEB Client `_on_time_expired` | `SessionGuard` tick thấy `<= 0` | Cửa sổ client còn sống |
| 3 | `deadline_sweeper` | Quá `deadline + 15s`, quét mỗi 30s | Luôn chạy (nếu backend sống) |

Trong thực tế chỉ **một** trong ba thắng, vì `submit_exam` kiểm tra
`session.status != "SUBMITTED"` trước khi làm gì. Hai bên còn lại nhận kết quả cũ.

**Vì sao cần cả ba:**

- Chỉ có React: đóng tab lúc hết giờ → phiên kẹt `IN_PROGRESS` vĩnh viễn, không
  bao giờ được chấm.
- Chỉ có SEB: thi bằng web thì không có client.
- Chỉ có sweeper: trễ tới 45s (15 grace + 30 chu kỳ), và phụ thuộc backend còn sống.

**Điều đáng chú ý:** SEB Client `_show_blocked()` **ẩn `web_view`** trước khi hiện
thông báo. Nếu client chỉ ẩn view mà không tự nộp, trang React bên trong mất cơ hội
gửi `POST /submit` — bài không bao giờ được chấm. Đó là lý do `_on_time_expired`
phải chủ động `POST` với `submit_type="AUTO_TIMEOUT"` trước khi chặn màn hình.

### 11.2. Vì sao heartbeat phải ghi vi phạm trước khi đổi trạng thái

Đoạn code dưới đây trông như có thể đảo thứ tự, nhưng không:

```python
# heartbeat_monitor.py:91
AnticheatService.record_violation(   # ← phải chạy trước
    db, session_id,
    ViolationLogCreate(event_type="CONNECTION_LOST", ...),
)
session.status = "DISCONNECTED"      # ← rồi mới đổi
db.commit()
```

`record_violation` có cổng:
```python
if not session or session.status != "IN_PROGRESS":
    return None, False
```

Nếu đổi `status` trước, lời gọi `record_violation` **trả về ngay mà không ghi gì**,
và bằng chứng "thí sinh mất kết nối 40 giây" biến mất khỏi `violation_logs`. Giảng
viên sẽ thấy phiên bị `DISCONNECTED` nhưng không có log giải thích tại sao.

Cùng lý do, `deadline_sweeper` không ghi vi phạm gì cả khi tự nộp — hết giờ không
phải hành vi gian lận.

---

## 12. Vòng đời một phiên thi

```
① Giảng viên tạo đề + ca thi
   POST /api/exams → POST /api/exams/schedules
   → sinh room_code (VD "PBL4-EXAM-01")

② Cấu hình khoá an toàn
   PUT /api/exams/{id}/security-policy  (chủ sở hữu đề)
   Cờ hệ thống: PUT /api/admin/settings/require-safe-browser   (ADMIN)

③ Thí sinh vào phòng
   POST /api/exam-sessions/join {room_code}
   ├─ kiểm tra ca đang mở
   ├─ resolve policy + kiểm tra SEB
   ├─ tạo/khôi phục ExamSession (IN_PROGRESS)
   └─ trả đề (không có đáp án) + policy + bộ đếm vi phạm

④ Kết nối realtime
   socket connect(auth={token})
   emit join_exam_room → server theo dõi heartbeat

⑤ Làm bài
   - click "Bắt đầu thi" → fullscreen + bật 7 guard
   - chọn đáp án → useAutoSave debounce 1.5s → POST save-answer
   - rời tab / thoát fullscreen → handleIncident → socket violation
     → server ghi log, cộng risk, (nếu vượt ngưỡng) tự nộp

⑥ Giảng viên giám sát
   /monitor/:scheduleId → join_monitor_room
   nhận violation_alert, student_status_change, student_force_submitted
   bấm "Thu bài" → teacher_force_submit

⑦ Kết thúc
   MANUAL        thí sinh bấm nộp → flush đáp án → POST submit
   AUTO_TIMEOUT  đồng hồ về 0 (React hoặc SEB Client) → POST submit
                 hoặc sweeper phát hiện quá hạn
   AUTO_VIOLATION vượt ngưỡng / giám thị cưỡng chế
   → status=SUBMITTED → grade_session() ngay → ExamResultResponse
```

---

## 13. Phân quyền

| Chức năng | ADMIN | TEACHER | STUDENT |
|---|---|---|---|
| Đăng nhập | ✓ | ✓ | ✓ |
| Quản lý người dùng | ✓ | — | — |
| Cấu hình hệ thống / cờ SEB toàn cục | ✓ | — | — |
| Thu hồi / mở khoá thiết bị | ✓ | — | — |
| Nhật ký thao tác | ✓ | — | — |
| Tạo/sửa đề | ✓ | chỉ đề mình tạo | — |
| Cấu hình khoá an toàn của đề | ✓ | chỉ đề mình tạo | — |
| Ngân hàng câu hỏi | ✓ | ✓ (dùng chung) | — |
| Tạo ca thi | ✓ | ✓ | — |
| Sửa ca thi | ✓ | chỉ ca mình phụ trách | — |
| Giám sát realtime + thu bài | ✓ | ✓ | — |
| Báo cáo / Excel / PDF | ✓ | chỉ ca mình phụ trách | — |
| Vào phòng thi | ✓ | ✓ | ✓ |
| Xem kết quả của mình | ✓ | ✓ | ✓ |

**Lưu ý:** đọc danh sách/chi tiết đề mở cho mọi TEACHER (ngân hàng đề dùng chung);
chỉ thao tác **ghi** và **báo cáo** mới bị giới hạn theo chủ sở hữu.

---

## 14. Danh mục API

### Auth
```
POST   /api/auth/login                    Đăng nhập JSON
POST   /api/auth/login-form               Đăng nhập OAuth2 form (Swagger)
POST   /api/auth/register                 Đăng ký công khai → LUÔN là STUDENT
GET    /api/auth/me                       Hồ sơ hiện tại
POST   /api/auth/client-devices           Đăng ký public key Ed25519
POST   /api/auth/client-nonce             Bước 1 challenge-response
POST   /api/auth/client-attest            Bước 2 challenge-response
```

### Exam session (thí sinh)
```
POST   /api/exam-sessions/join            Vào phòng
POST   /api/exam-sessions/save-answer     Lưu đáp án
POST   /api/exam-sessions/submit          Nộp bài + chấm điểm
GET    /api/exam-sessions/my-results      Kết quả của mình
GET    /api/exam-sessions/{token}/identity  Định danh client của phiên
```

### Exams & schedules
```
GET/POST      /api/exams
GET/PUT/DELETE /api/exams/{exam_id}
GET           /api/exams/schedules/list
POST          /api/exams/schedules
PUT           /api/exams/schedules/{schedule_id}
GET/PUT       /api/exams/{exam_id}/security-policy
```

### Questions
```
GET/POST      /api/questions
GET/PUT/DELETE /api/questions/{question_id}
GET/POST      /api/questions/subjects
GET           /api/questions/import/template
POST          /api/questions/import/preview
POST          /api/questions/import/commit
```

### Reports
```
GET  /api/reports/schedules/{id}/statistics
GET  /api/reports/schedules/{id}/export-excel
GET  /api/reports/schedules/{id}/export-pdf
GET  /api/reports/sessions/{id}/violations
```

### Admin
```
GET/POST      /api/admin/users
GET           /api/admin/users/stats
PUT/DELETE    /api/admin/users/{user_id}
POST          /api/admin/users/{user_id}/reset-password
GET           /api/admin/audit-logs
GET           /api/admin/audit-logs/actions
GET           /api/admin/settings
GET/PUT       /api/admin/settings/require-safe-browser
PUT           /api/admin/settings/seb-client-config
PUT           /api/admin/settings/default-security-config
GET           /api/admin/devices
POST          /api/admin/devices/{device_id}/revoke
```

---

## 15. Cấu hình & triển khai

### Biến môi trường (`backend/.env`)

| Biến | Mặc định (dev) | Ghi chú |
|---|---|---|
| `ENV` | `development` | `production` bật kiểm tra an toàn |
| `DEBUG` | `true` | |
| `SECRET_KEY` | (giá trị dev) | **Bắt buộc đổi** khi production; dùng để ký JWT và dẫn xuất `device_secret` |
| `DATABASE_URL` | `mysql+pymysql://root:@127.0.0.1:3306/secure_exam_db` | Production phải có mật khẩu |
| `CORS_ORIGINS` | localhost:5173, 127.0.0.1:5173, localhost:3000 | Production không được chứa `*` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 480 | |
| `DEFAULT_MAX_VIOLATION_ALLOWED` | 5 | Bậc 3 của ngưỡng |
| `HEARTBEAT_INTERVAL_SECONDS` | 10 | Chu kỳ client gửi |
| `HEARTBEAT_TIMEOUT_SECONDS` | 30 | Ngưỡng bị coi là mất kết nối |
| `CLIENT_NONCE_TTL_SECONDS` | 30 | Nonce attestation |

### Chạy dev

```bash
# Backend
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python seeders/seed_data.py          # tạo dữ liệu mẫu
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxy /api và /socket.io → :8000)

# SEB Client
cd seb_client
.venv/bin/python -m sebclient
```

### Tài khoản seed

| Vai trò | Username | Mật khẩu |
|---|---|---|
| Quản trị | `admin` | `admin123` |
| Giảng viên | `teacher1` | `teacher123` |
| Sinh viên | `student1`, `student2` | `student123` |

Mã phòng mẫu: `PBL4-EXAM-01` (seeder tự lùi khung giờ về hiện tại nếu đã hết hạn).

### Frontend → Backend

`vite.config.js` proxy `/api` và `/socket.io` (kể cả `ws: true`) về
`http://127.0.0.1:8000`, nên dev không vướng CORS.

### Kiểm thử

```bash
cd backend && .venv/bin/python -m pytest tests -q
cd frontend && npm run lint && npm run build
cd seb_client && .venv/bin/python -m pytest tests -q
./seb_client/run_windows_tests.sh    # Win32 thật qua Wine (nếu có)
```

### Triển khai production

Phần này **không** lặp lại ở đây vì có tài liệu riêng:
**[`docs/deploy/TRIEN_KHAI_WEB_VA_SEB.md`](deploy/TRIEN_KHAI_WEB_VA_SEB.md)**.

Nội dung then chốt của tài liệu đó:

| Mục | Vì sao phải đọc |
|---|---|
| Ba danh sách origin phải khớp (`CORS_ORIGINS` / `SEB_ALLOWED_ORIGINS` / `SEB_EXAM_URL_TEMPLATE`) | Lệch nhau → CORS fail hoặc client reload vô hạn |
| `embedded=1` bắt buộc | Thiếu → `DUPLICATE_LOGIN` → buộc nộp bài |
| Mẫu nginx (SPA fallback + WebSocket upgrade + timeout) | Thiếu SPA fallback → F5 giữa giờ ra 404; thiếu upgrade → socket rơi về polling |
| `--workers 1`, `ENV=production`, UTC hai phía | Ba điều kiện âm thầm phá hệ thống nếu sai |
| Checklist 3 nhóm trước khi cho thi | Gồm 9 bước kiểm web ↔ SEB |
| Bảng chẩn đoán 9 triệu chứng | Tra nhanh khi có sự cố |

Bản đóng gói SEB Client: `seb_client/packaging/HUONG_DAN_DONG_GOI.md` (build
Linux/Windows, cấu hình `.env` cạnh file chạy).

---

## 16. Giới hạn kỹ thuật (trung thực)

Xem đầy đủ tại `docs/BAOCAO_LIMITATION.md`. Tóm tắt những điểm **phải nêu** trong báo cáo:

| Giới hạn | Lý do |
|---|---|
| Tổ hợp phím do OS xử lý trước trình duyệt | Alt+Tab, phím Windows: web không chặn được; chỉ phát hiện hậu quả |
| Phần mềm chụp màn hình / thiết bị ngoài | Ngoài phạm vi mọi cơ chế phần mềm |
| Thiết bị thứ hai | Không phát hiện được |
| Phát hiện DevTools chỉ là heuristic | DevTools dạng cửa sổ tách rời không bị phát hiện |
| Tắt JavaScript / extension | Lớp web mất tác dụng |
| Cảnh báo Mức 2 không bảo đảm thí sinh nhìn màn hình | Chỉ là thông báo |
| "Only through SEB" là ghi nhận, không phải chặn tuyệt đối | Gọi API trực tiếp vẫn vào được, chỉ để lại log `UNAUTHORIZED_CLIENT` |
| Thu hồi thiết bị theo `device_id` có thể lách bằng khoá mới | Cần thêm giới hạn số thiết bị / admin duyệt |
| `active_sockets`, `_pending_nonces` là in-memory | Multi-worker cần Redis |
| Đường HMAC cũ vẫn hỗ trợ | Tương thích ngược cho client chưa nâng cấp |
| `slowapi` có trong requirements nhưng chưa gắn | Hiện chưa có rate limit thực tế |
| F5 nhanh (hoặc React StrictMode) sinh `DUPLICATE_LOGIN` dương tính giả | Socket cũ chưa kịp `disconnect` → +25 risk score oan |
| SEB Client **bỏ qua** `security_policy` server trả về | Client luôn bật đủ 7 guard; GV tắt `block_copy_paste` thì web tôn trọng, SEB vẫn chặn |
| Guard DOM của web vẫn chạy khi `embedded=1` | Chỉ socket + `logViolation` được bỏ → `strikes` cục bộ có thể lệch server |
| Heuristic DevTools vô dụng trong webview | Trong `QWebEngineView`, `outerWidth < innerWidth` (probe: 328 vs 900) → không bao giờ phát hiện |
| `X-Client-Required` được `expose_headers` nhưng không nơi nào set | Hợp đồng chết, không ảnh hưởng hoạt động |
| `SebClientConfig.attestation_required` không được enforce | Bật cờ này không có tác dụng |
| `hashedQuitPassword` trong file `.seb` chỉ được đọc | Chưa có hộp thoại nhập mật khẩu giám thị để mở khoá thoát |
| Chế độ `.seb` không giám sát, không đếm vi phạm, không tự nộp | Không có backend để gửi/nhận |

### 16.1. Ba việc đã vá trong đợt gần nhất (để không báo cáo sai là "chưa làm")

| Lỗi | Triệu chứng thật | Cách vá |
|---|---|---|
| `requestFullscreen()` không bao giờ settle trong webview | Bấm "Bắt đầu thi" không có gì xảy ra (probe: promise `pending`) | Nối `page.fullScreenRequested` → `accept()` + `showFullScreen()` |
| Webview không gửi header định danh | Thí sinh dùng SEB vẫn thấy PolicyGate + `UNAUTHORIZED_CLIENT` oan | `ClientIdentityInterceptor` + attest lại mỗi 240s |
| Nộp bài xong kẹt trong kiosk | Không đóng được cửa sổ ở trang kết quả | `urlChanged` → phát hiện `/exam/results` → `_show_blocked()` |

---

## Phụ lục A — Bản đồ mã nguồn nhanh

```
backend/app/
  main.py                  Khởi tạo FastAPI + mount Socket.IO ASGI + 2 task nền
  api/routers/             8 router (HTTP) — chỉ điều phối
  core/                    config · database · security
  dependencies/            auth · client_identity · exam_time · ownership
  models/                  16 ORM
  schemas/                 Pydantic request/response
  services/                16 service nghiệp vụ
  sockets/                 socket_server · socket_auth · exam_namespace · monitor_namespace

frontend/src/
  App.jsx                  Router theo role
  pages/exam/ExamRoom.jsx  State machine phòng thi (933 dòng)
  pages/exam/PolicyGate.jsx Màn "đề yêu cầu SEB"
  pages/exam/hooks/        8 hook khoá an toàn
  services/                apiClient · socketClient · policyService · teacherService
  store/authStore.js       Zustand

seb_client/sebclient/
  app.py                   Quyết định 2 chế độ + qasync loop
  config.py                ClientConfig từ .env (hoặc cạnh file chạy khi frozen)
  config_file.py           Parser .seb → BrowserPolicy
  make_seb.py              Công cụ tạo file .seb
  api/                     client · attestation · heartbeat
  guards/                  7 guard
  osint/                   adapter OS + keystore
  ui/                      login · exam_window · policy_browser_window ·
                           request_interceptor · web_page · overlays

docs/
  KIEN_TRUC_VA_NGHIEP_VU.md      ← tài liệu này
  deploy/TRIEN_KHAI_WEB_VA_SEB.md  Hướng dẫn triển khai + nginx
  BAOCAO_LIMITATION.md             Giới hạn kỹ thuật (bắt buộc theo đề cương)
  PLAN.md · SEB_CLIENT_SPEC.md · SEB_GATE_DESIGN.md
```

## Phụ lục B — Điểm nối giữa các lớp

| Việc cần làm | Lớp A (Web) | Lớp B (SEB) | Backend |
|---|---|---|---|
| Lấy policy | response `join` | response `join` | `resolve_policy()` |
| Báo vi phạm | socket `violation` | guard → socket `violation` | `record_violation()` |
| Nhận lệnh thu bài | socket `force_submit` | socket `force_submit` | `submit_exam()` |
| Nộp khi hết giờ | React `submitExam('AUTO_TIMEOUT')` | `_on_time_expired` → `ApiClient.submit_exam` | sweeper |
| Xác thực client | `X-Client-Type: web` | Ed25519 + attestation token + **interceptor cho webview** | `verify_attestation()` |
| Giữ nhịp | socket `heartbeat` | `ExamSocket` heartbeat | `heartbeat_monitor` |
| Vào fullscreen | `document.documentElement.requestFullscreen()` | trang web gọi → `fullScreenRequested` → Qt | — |
| Biết đã nộp | `navigate('/exam/results')` | `urlChanged` → `_show_blocked()` | — |

## Phụ lục C — Câu hỏi thường gặp khi đọc code

**"Tại sao `ExamRoom.jsx` dài 933 dòng mà không tách?"**
Vì 8 hook chia sẻ chung 4 `ref` (`submittingRef`, `submittedRef`, `autoSubmitFiredRef`,
`strikesRef`) và một state machine duy nhất (`inProgress`). Tách ra sẽ phải truyền
các ref qua props hoặc context, làm khó thấy được quan hệ "một hành động chỉ đếm
một lần". Đổi lại, phần hiển thị đã tách thành component riêng (PolicyGate,
WarningOverlay...).

**"Tại sao có cả `useState` và `useRef` cho cùng một giá trị?"**
Xem bảng ở mục 6.5: `state` để render, `ref` để đọc đồng bộ trong callback. Không
phải trùng lặp — chúng giải quyết hai vấn đề khác nhau.

**"Router có được query DB trực tiếp không?"**
Theo quy ước (mục 1.3): không. Hiện có vài chỗ vi phạm nhẹ (router đọc `session`
để trả kèm `attestation_status`), nhưng không có nghiệp vụ nào nằm ở router.

**"Vì sao `resolve_policy` gọi `is_safe_browser_required` riêng thay vì trả trong policy?"**
Vì hai thứ khác bản chất: `policy` là 12 cờ cơ chế, còn `require_safe_browser` là
phép AND giữa cấu hình đề và cấu hình hệ thống. Gộp vào một schema sẽ khiến người
đọc tưởng nó cũng là một cờ bật/tắt đơn giản.

**"Làm sao biết một vi phạm có thật sự tới server?"**
Kiểm `violation_logs` trong DB. Nếu UI hiện cảnh báo mà bảng rỗng: socket chưa kết
nối (xem log backend) hoặc đang ở `embedded=1` (client tự gửi, không phải web).

---

*Tài liệu đối chiếu mã nguồn ngày 2026-11-12 (sau các bản vá P0) và knowledge graph
`graphify-out/graph.json` (2050 node · 5455 cạnh · 115 cộng đồng).*
*Sau khi sửa code, chạy `graphify update .` để cập nhật graph (chỉ AST, không tốn API).*
