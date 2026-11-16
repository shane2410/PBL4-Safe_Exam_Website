# TÓM TẮT ĐẶC TẢ YÊU CẦU PHẦN MỀM (SRS v3 SUMMARY)
## Hệ thống Thi trắc nghiệm trực tuyến An toàn (Secure Online Exam System)

> **Tài liệu tham chiếu:** Cập nhật và thay thế phạm vi "web-only" của SRS v2 (`SRS_He_thong_thi_truc_tuyen_v2.docx`).
>
> Tổng hợp các quyết định kỹ thuật cốt lõi từ [`docs/PLAN.md`](PLAN.md), [`docs/SEB_GATE_DESIGN.md`](SEB_GATE_DESIGN.md), [`docs/SEB_CLIENT_SPEC.md`](SEB_CLIENT_SPEC.md) và [`docs/BAOCAO_LIMITATION.md`](BAOCAO_LIMITATION.md).

---

## 1. Phân biệt kiến trúc hai lớp: Web Client (Lớp A) và SEB Client (Lớp B)

Trong SRS v3, hệ thống chuyển dịch từ mô hình thuần Web sang **kiến trúc bảo vệ hai lớp song song**, cùng kết nối tới một backend FastAPI duy nhất:

| Tiêu chí | Lớp A — Web Client | Lớp B — SEB Client (Desktop) |
|---|---|---|
| **Công nghệ** | React 18, Vite, TailwindCSS, Zustand | Python 3.11+, PySide6 (Qt 6 WebEngine), `qasync` |
| **Môi trường chạy** | Trình duyệt Web tiêu chuẩn (Chrome, Edge, Firefox, Safari) | Ứng dụng Desktop chạy trực tiếp trên Windows, macOS, Linux |
| **Cài đặt** | Không cần cài đặt, truy cập qua URL | Cài đặt ứng dụng hoặc chạy bản đóng gói độc lập (`onedir`) |
| **Phạm vi bảo vệ** | Tầng ứng dụng Web / DOM (Tab-level isolation) | Tầng hệ điều hành (OS-level isolation & system hooks) |
| **Khả năng kiểm soát** | Bắt sự kiện bàn phím trên DOM, fullscreen API trình duyệt, `visibilitychange`, `blur` | Chặn tổ hợp phím hệ thống (`Alt+Tab`, `Win`), khóa chuột/clipboard, Kiosk toàn màn hình, chặn chụp màn hình |
| **Xác thực Client (Attestation)** | Không có attestation thiết bị (`client_type = web`, `attestation_status = NOT_ATTESTED`) | Xác thực cặp khóa bất đối xứng Ed25519 gắn với phần cứng (`client_type = seb`, `attestation_status = VERIFIED`) |
| **Trường hợp sử dụng** | Bài kiểm tra thường xuyên, điều kiện phòng thi linh hoạt, làm bài dự phòng | Bài thi chính thức, kỳ thi chuẩn hóa, phòng thi máy tính có giám sát |

### Nguyên tắc bất biến
Mọi logic nghiệp vụ, quản lý ngân hàng câu hỏi, sinh đề thi, chấm điểm, quản lý thời gian và quyết định thu bài **100% nằm ở Backend FastAPI**. Cả Web Client và SEB Client chỉ đóng vai trò là giao diện hiển thị và thu thập sự kiện tương tác của thí sinh.

---

## 2. Cơ chế `require_safe_browser`

Cơ chế `require_safe_browser` là tính năng trọng tâm giải quyết yêu cầu *"cho phép bật/tắt chỉ thi qua Safe Exam Browser"*.

### 2.1. Công thức quyết định hiệu lực

Quyết định bắt buộc thi qua Safe Exam Browser được hợp nhất tại backend qua hàm `ExamSecurityService.is_safe_browser_required()`:

$$\text{SEB\_REQUIRED} = (\text{exam.require\_safe\_browser} == \text{true}) \land (\text{system\_settings.require\_safe\_browser\_global} == \text{true})$$

- **Cấp hệ thống (`system_settings`):** Quản trị viên (Admin) cấu hình chính sách toàn trường.
- **Cấp đề thi (`exams`):** Giảng viên (Teacher) có thể linh hoạt tắt yêu cầu cho từng đề cụ thể ngay cả khi toàn trường đang bật, tránh trường hợp một đề thi đặc thù chặn thí sinh không có máy tính cá nhân tương thích.

### 2.2. Luồng quyết định trạng thái phiên thi

```
                      Thí sinh vào phòng thi
                                │
                    SEB_REQUIRED == true ?
                                │
                 ┌──────────────┴──────────────┐
               KHÔNG                          CÓ
                 │                             │
        Cho phép cả Web & SEB          Xác thực Client
        - Web: NOT_ATTESTED            (Ed25519 Challenge)
        - SEB: VERIFIED                        │
                                       ┌───────┴───────┐
                                     Thành công      Thất bại / Dùng Web
                                       │               │
                                   VERIFIED       REQUIRED_MISSING
                               (Chế độ chuẩn)    (restricted_mode = true)
                                                       │
                                              - Ghi log UNAUTHORIZED_CLIENT (HIGH)
                                              - Frontend hiện màn hình PolicyGate
                                              - Thí sinh để lại dấu vết phục tra
```

### 2.3. Trạng thái `restricted_mode` và cờ `allow_web_fallback`

- **Mục đích:** Tuân thủ nguyên tắc **RĂN ĐE VÀ GHI NHẬN BẰNG CHỨNG**, không chặn cứng gây tắc nghẽn phòng thi.
- Khi một đề thi yêu cầu SEB nhưng thí sinh cố tình vào bằng Web Client:
  1. Server vẫn tạo phiên thi nhưng đánh dấu `restricted_mode = true` và `attestation_status = REQUIRED_MISSING`.
  2. Ghi một bản ghi `UNAUTHORIZED_CLIENT` vào bảng `violation_logs` với mức nghiêm trọng `HIGH`.
  3. Phía Web Client, component `PolicyGate.jsx` sẽ chặn hiển thị bài thi, thông báo thí sinh cần chuyển sang dùng SEB Client.
- **Phân tích `allow_web_fallback`:**
  - Nếu giảng viên bật `allow_web_fallback = true` trong cấu hình đề, thí sinh có thể bấm *"Tiếp tục thi bằng Web với chế độ hạn chế"* để làm bài.
  - *Hiện trạng kỹ thuật:* Hiện tại `allow_web_fallback` mới được thi hành ở giao diện Frontend (`PolicyGate.jsx`). Nếu gọi trực tiếp API `POST /api/exam-sessions/join` bằng script, server vẫn tạo phiên. Thiết kế hoàn thiện tầng backend sẽ trả về mã lỗi `HTTP 403 SEB_REQUIRED` khi `allow_web_fallback = false`.

---

## 3. Cơ chế xác thực định danh Client (Challenge-Response)

Để ngăn chặn việc giả mạo header HTTP (như gửi `X-Client-Type: seb` bằng Postman/curl), hệ thống triển khai cơ chế thách thức - phản hồi mật mã học.

### 3.1. Mô hình HMAC-SHA256 (Phase 0 — Khóa đối xứng)
1. Thí sinh đăng nhập nhận JWT Bearer token.
2. Client gọi `POST /api/auth/client-nonce` để nhận `nonce` ngẫu nhiên 32 bytes (hạn sử dụng 30 giây, lưu in-memory trên server).
3. Client dẫn xuất khóa bí mật:
   $$\text{device\_secret} = \text{HMAC-SHA256}(\text{key} = \text{SECRET\_KEY}, \text{msg} = \text{"device\_secret"}\mid\text{user\_id}\mid\text{salt})$$
4. Client ký thông điệp:
   $$\text{signature} = \text{base64}(\text{HMAC-SHA256}(\text{key} = \text{device\_secret}, \text{msg} = \text{nonce}\mid\text{client\_version}\mid\text{device\_fingerprint}))$$
5. Client gửi chữ ký lên `POST /api/auth/client-attest`. Server kiểm tra và xóa nonce ngay lập tức để chống Replay Attack.
- *Nhược điểm:* Khóa đối xứng buộc bí mật phải chia sẻ hoặc tính toán trong bộ nhớ RAM của client; nếu `SECRET_KEY` bị lộ, kẻ tấn công có thể giả mạo chữ ký.

### 3.2. Mô hình Ed25519 (Phase 1 — Khóa bất đối xứng)
1. **Khởi tạo khóa trên thiết bị:** SEB Client tự sinh một cặp khóa Ed25519 (raw 32 bytes).
   - Khóa riêng (Private Key): Lưu trữ cục bộ trong Keystore an toàn của hệ điều hành (Windows DPAPI, macOS Keychain, Linux Secret Service). **Khóa riêng tuyệt đối không bao giờ rời khỏi thiết bị**.
   - Khóa công khai (Public Key): Được client gửi lên server để đăng ký thông qua `POST /api/auth/client-devices`.
2. **Đăng ký thiết bị:** Server tính toán định danh thiết bị duy nhất:
   $$\text{device\_id} = \text{sha256}(\text{public\_key})[:16]$$
   và lưu trữ bản ghi vào bảng `client_devices`.
3. **Thách thức - Phản hồi:**
   - Server phát sinh `nonce` ngẫu nhiên (TTL 30s).
   - Client dùng **Private Key** ký lên chuỗi thông điệp `nonce|client_version|device_fingerprint|device_id`.
   - Server dùng **Public Key** đã đăng ký của thiết bị để xác minh chữ ký tại endpoint `POST /api/auth/client-attest`.
4. **Ưu điểm vượt trội:**
   - Server không lưu trữ khóa riêng, do đó dù cơ sở dữ liệu server hoặc `SECRET_KEY` có bị rò rỉ, kẻ tấn công vẫn **không thể tạo chữ ký thay thế cho thiết bị của thí sinh**.
   - Mỗi phiên thi gắn chặt với một `device_id` đã được xác thực, chống gian lận dùng nhiều máy hoặc chia sẻ token.

---

## 4. Bảo mật phân tầng & Mô hình đe dọa (Bảng 2.2)

Hệ thống thiết kế theo nguyên tắc phòng thủ nhiều lớp (Defense-in-Depth). Chi tiết ma trận đe dọa và đánh giá khả năng đối phó:

| # | Mối đe dọa | Biện pháp kỹ thuật | Mức độ | Ghi chú trung thực (Đánh giá học thuật) |
|---|---|---|---|---|
| **C1** | Giả mạo header `X-Client-Type: seb` bằng công cụ HTTP (curl, Postman) | Thách thức chữ ký Ed25519 gắn với thiết bị đã đăng ký; kết hợp nonce một lần (Phase 0 dùng HMAC) | **Cao** | Kẻ tấn công phải đăng nhập tài khoản thi thật và phải sở hữu khóa riêng trên thiết bị hợp lệ. |
| **C2** | Tấn công phát lại (Replay Request đã bắt được trên đường truyền) | Nonce có TTL 30 giây, dùng một lần bị xóa ngay; chữ ký phủ cả `nonce\|version\|fingerprint` | **Cao** | Đã triển khai và có test case kiểm chứng tự động (`test_phase0_security.py`). |
| **C3** | Đánh cắp đáp án đúng từ lưu lượng mạng (Sniffing traffic) | DTO `QuestionPublic` trả về client hoàn toàn không có trường `is_correct` | **Cao** | Server nắm giữ toàn bộ đáp án và thực hiện chấm điểm độc lập. |
| **C4** | Sửa đổi file nhị phân / Patch file `.exe` client | Self-check hash SHA-256 đối chiếu giá trị nhúng; biên dịch mã nguồn nhạy cảm sang mã máy (C++/pybind11) | **Thấp–TB** | Mã tự kiểm tra nằm trong chính binary cần bảo vệ nên có thể bị bypass bằng kỹ thuật dịch ngược (Reverse Engineering). Đây là rào chắn đồ án, không phải DRM thương mại. |
| **C5** | Dùng Debugger can thiệp tiến trình (x64dbg, IDA, Cheat Engine, GDB) | Tích hợp module `anti_debug` gọi API hệ thống (`IsDebuggerPresent`, `P_TRACED`, `/proc/self/status`); từ chối vào phòng nếu phát hiện | **Thấp–TB** | Chỉ phát hiện được debugger chạy ở chế độ User-mode tiêu chuẩn. Không chống được Kernel-level debugger. |
| **C6** | Đóng gói và phát tán phiên bản SEB Client đã bị bẻ khóa | Quản lý danh sách hash chính thức trên server (`signed_client_releases`); kết hợp ký số Code Signing (Authenticode / Notarization) | **TB–Cao** | Biện pháp ngăn chặn phát tán diện rộng hiệu quả nhất trong thực tế. |
| **C7** | Đọc mã nguồn Python để tìm lỗ hổng logic | Đóng gói nhị phân độc lập bằng PyInstaller/Nuitka; biên dịch các module quan trọng sang C++ native extension | **TB** | Nâng cao độ phức tạp và chi phí phân tích mã nguồn đối với thí sinh thông thường. |
| **C8** | Chạy client trong máy ảo (VM) để thao tác ở máy thật bên ngoài | Đánh giá rủi ro phát hiện VM: **Quyết định KHÔNG chặn cứng** | **Thấp** | Nằm ngoài phạm vi đồ án. Phát hiện VM dễ gây báo sai nghiêm trọng (máy lab trường học chạy VDI, laptop dùng Hyper-V/WSL). Rủi ro bất công cho thí sinh lớn hơn lợi ích bảo mật. |
| **C9** | Đăng nhập đồng thời trên nhiều máy / chia sẻ phiên | Server-side `DuplicateLoginGuard`: Mỗi phiên chỉ duy trì một WebSocket connection hoạt động; kết nối mới đá kết nối cũ kèm log vi phạm | **Cao** | Cơ chế cưỡng chế hoàn toàn ở server, không thể bị qua mặt bằng cách chỉnh sửa client. |
| **C10** | Thí sinh rút dây mạng / ngắt kết nối để né giám sát | Server chạy `heartbeat_monitor` quét định kỳ: Đánh dấu `DISCONNECTED` sau 30s im lặng; hết hạn nộp bài thì tự động thu bài | **Cao** | Server chủ động xử lý dựa trên đồng hồ hệ thống. |
| **C11** | Sửa đồng hồ hệ thống trên máy tính để kéo dài thời gian làm bài | **Server là nguồn sự thật duy nhất về thời gian**: Client chỉ nhận mốc `deadline` UTC; server từ chối ghi nhận đáp án sau khi hết giờ | **Cao** | Đã triển khai và có test case kiểm chứng tự động. |
| **C12** | **Vá trực tiếp hàm bảo vệ client (cho `enter_kiosk()` thành `pass`) nhưng giữ nguyên mã attestation** | Không có biện pháp kỹ thuật nào ở tầng client có thể chặn triệt để | **Không chặn được** | **Mối đe dọa bản chất của phần mềm chạy trên máy người dùng.** Cần kết hợp phân tích hành vi bất thường trên server (mục C14). |
| **C13** | Lộ khóa bí mật hệ thống (`SECRET_KEY`) | Chuyển sang mô hình Ed25519 với khóa riêng nằm tại máy trạm; nạp cấu hình từ biến môi trường | **Trung bình** | Sau khi chuyển sang Ed25519, việc lộ `SECRET_KEY` không còn đủ để giả lập attestation thiết bị của thí sinh. |
| **C14** | **Client bị bẻ khóa im lặng hoàn toàn (không gửi bất kỳ log vi phạm nào)** | Server không coi "nhật ký sạch" là bằng chứng tuyệt đối; kết hợp phân tích thời gian trả lời và giám sát trực tiếp của giám thị | **Không chặn được** | Mọi vi phạm ghi nhận chỉ có giá trị hỗ trợ phúc tra khi có bằng chứng, không dùng để kết luận tuyệt đối. |

---

## 5. Giới hạn kỹ thuật trung thực (Technical Limitations)

Trích dẫn từ [`docs/BAOCAO_LIMITATION.md`](BAOCAO_LIMITATION.md), hệ thống công khai các giới hạn kỹ thuật không thể vượt qua ở mức độ ứng dụng:

1. **Tổ hợp phím cấp hệ điều hành:** Các phím nóng như `Alt+Tab`, `Cmd+Tab`, phím `Windows` được kernel hệ điều hành xử lý trước khi sự kiện tới được trình duyệt Web. Do đó Web Client chỉ ghi nhận được hệ quả sau khi cửa sổ đã mất tiêu điểm (`blur`), không thể ngăn chặn hành động chuyển cửa sổ.
2. **Thiết bị ghi hình và màn hình ngoài:** Phần mềm không thể phát hiện thí sinh sử dụng điện thoại chụp ảnh màn hình, sử dụng màn hình phụ không khai báo qua card đồ họa, hoặc có người trợ giúp ngồi bên ngoài góc quan sát của webcam.
3. **Môi trường đồ họa Linux Wayland:** Giao thức Wayland có kiến trúc bảo mật cô lập giữa các tiến trình, không cho phép một ứng dụng tự ý truy vấn thông tin cửa sổ đang chiếm tiêu điểm (Active Window Title) như X11 hoặc Win32 API.
4. **Giới hạn kiểm thử tải:** Hệ thống hiện tại vận hành ở mô hình một worker (`uvicorn --workers 1`) do cơ chế nonce in-memory. Kiểm thử tải mới được thực hiện qua kịch bản mô phỏng cục bộ (`locustfile.py`), chưa kiểm chứng trên cụm phân tán quy mô lớn.

### Kết luận giá trị thực tế
Giá trị bảo vệ thực tế của hệ thống không nằm ở việc tạo ra một "phần mềm không thể bẻ khóa", mà nằm ở chỗ:
- **Tăng chi phí và độ phức tạp kỹ thuật** của hành vi gian lận lên mức rất cao so với việc học bài nghiêm túc.
- **Bảo toàn tính toàn vẹn của đề thi và điểm số:** Đề thi không có đáp án đúng, server giữ quyền tính điểm và chốt thời gian.
- **Lưu vết và phân loại minh bạch:** Cung cấp đầy đủ bằng chứng kiểm toán (`violation_logs`, `client_attestations`) giúp hội đồng thi và giảng viên có cơ sở chính xác khi xử lý khiếu nại hoặc phục tra bài thi.
