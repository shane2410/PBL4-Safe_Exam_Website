# GIỚI HẠN KỸ THUẬT CỦA HỆ THỐNG

> **Tài liệu bắt buộc theo yêu cầu đề cương (skills.md Quy tắc #5).**
> Mục đích: trình bày thẳng thắn những gì hệ thống **không** làm được, để giá trị
> thực tế của các cơ chế bảo mật không bị đánh giá sai.

---

## 1. Nguyên tắc trung thực

Mọi cơ chế khoá an toàn trong đồ án này hoạt động ở **tầng trình duyệt và tầng ứng dụng**,
tức là **trên máy của chính thí sinh**. Về bản chất, chúng mang tính **RĂN ĐE và GHI NHẬN
BẰNG CHỨNG**, không phải ngăn chặn tuyệt đối.

Mục tiêu thực tế của hệ thống không phải là "không ai gian lận được", mà là:

1. **Làm cho hành vi gian lận tốn kém hơn nhiều** so với làm bài nghiêm túc.
2. **Luôn để lại bằng chứng** để hỗ trợ phúc tra và xử lý khiếu nại về sau.
3. **Phân biệt được** phiên thi hợp lệ với phiên thi không vượt qua kiểm chứng.

---

## 2. Những gì hệ thống KHÔNG chặn được

### 2.1 Tổ hợp phím do hệ điều hành xử lý

`Alt+Tab`, `Cmd+Tab`, phím `Win`, `Ctrl+Alt+Delete` được **hệ điều hành xử lý trước khi
sự kiện tới được trình duyệt**. JavaScript không thể `preventDefault` những tổ hợp này.

→ Hệ thống chỉ **phát hiện hậu quả** qua sự kiện `blur` / `visibilitychange` **sau khi**
thí sinh đã chuyển sang cửa sổ khác. Đây là phát hiện *sau sự kiện*, không phải ngăn chặn.

### 2.2 Phần mềm chụp màn hình và thiết bị ngoài

In Lớp A (web), hệ thống **không thể** chặn phần mềm chụp màn hình chạy ở tầng hệ
điều hành (Snipping Tool, Lightshot, OBS…), hoặc camera ghi lại màn hình từ bên ngoài.

→ Chỉ có thể phát hiện một số trường hợp ở **tầng ứng dụng** (đây là phạm vi của
Safe Exam Browser Client ở Phase 1, xem bảng năng lực theo hệ điều hành trong
`docs/PLAN.md` mục 1.3).

### 2.3 Thiết bị thứ hai

Thí sinh dùng điện thoại, máy tính khác, hoặc thiếu bút ghi âm đặt ngay ngoài tầm
quan sát của bất kỳ phần mềm nào chạy trên máy tính.

→ **Nằm hoàn toàn ngoài khả năng kỹ thuật của đồ án.** Muốn xử lý phải bổ sung quy
định kỷ luật và giám sát trực tiếp của giám thị.

### 2.4 Heuristic phát hiện DevTools

Cơ chế phát hiện DevTools dựa trên kích thước cửa sổ (`outerWidth/innerWidth`):

- **DevTools mở dạng cửa sổ tách rời (undocked)** → **KHÔNG bị phát hiện**.
- Trình duyệt tuỳ biến hoặc chạy trong môi trường lạ → có thể báo sai.
- Người dùng thu nhỏ/phóng to cửa sổ, đổi tỉ lệ zoom của hệ điều hành → có thể báo nhầm.

→ Vì vậy hệ thống dùng ngưỡng trước nghiêng + yêu cầu điều kiện kéo dài để **giảm
báo nhầm**, nhưng không thể loại bỏ hoàn toàn.

### 2.5 Tắt JavaScript hoặc dùng tiện ích mở rộng

Thí sinh có thể tắt JavaScript trong trình duyệt, hoặc dùng tiện ích mở rộng can thiệp
vào trang để vô hiệu hoá một phần cơ chế khoá.

→ Server phát hiện **gián tiếp** qua việc **thiếu heartbeat** hoặc thiếu sự kiện
trong thời gian dài. Đây là phát hiện *hậu quả*, không phải ngăn chặn.

### 2.6 Cửa sổ cảnh báo Mức 2 không bảo đảm thí sinh nhìn màn hình

Khi thí sinh chuyển tab, hệ thống hiện cửa sổ cảnh báo đếm ngược. Thí sinh **có thể để
cửa sổ cảnh báo chạy ở nền** và tiếp tục làm việc khác.

→ Hết thời gian đếm ngược sẽ được tính là vi phạm nghiêm trọng, nhưng việc xác minh
"thí sinh có thực sự nhìn màn hình hay không" thuộc phúc tra, không thuộc phần mềm.

---

## 3. Hạn chế của cơ chế "only through safe exam browser"

Cờ `require_safe_browser` **không phải** cơ chế ngăn thí sinh dùng trình duyệt thường.
Thí sinh vẫn có thể truy cập bằng Chrome/Edge/Firefox bình thường.

Điều cờ này làm là:

1. Server **đánh dấu phiên thi đó là "restricted mode"** (`attestation_status = REQUIRED_MISSING`).
2. Ghi log `UNAUTHORIZED_CLIENT` với mức nghiêm trọng **HIGH** — làm bằng chứng phục tra.
3. Giao diện hiển thị màn hình hướng dẫn cài Safe Exam Browser Client.

Nó **không** làm là:

- Không khoá truy cập web.
- Không ngăn thí sinh làm bài bằng web.
- Không ảnh hưởng tới điểm số theo bất kỳ cơ chế tự động nào.

> **Lưu ý khi trình bày:** không nên mô tả cờ này là "bắt buộc dùng trình duyệt chuyên dụng"
> một cách tuyệt đối. Cách nói chính xác là: *"hệ thống phân biệt và ghi nhận phiên thi
> không vượt qua xác thực"*.

---

## 4. Hạn chế của cơ chế chống giả mạo client

Cơ chế dùng **nonce một lần + chữ ký Ed25519 bằng cặp khoá sinh trên máy**: private
key nằm trong kho hệ thống (DPAPI / Keychain / Secret Service), public key đăng ký lên
server. Server xác minh bằng public key — tức là **server không thể tự ký thay client**.

**Nó chống được:** giả header bằng `curl`/Postman, chơi lại request đã bắt, sao chép
khoá của một máy sang máy khác (máy khác chưa đăng ký public key đó).

**Nó KHÔNG chống được:** kẻ tấn công chiếm được máy thí sinh ở mức hệ điều hành vẫn
đọc được private key trong kho hệ thống. Đây là giới hạn bản chất của mọi cơ chế chống
giả mạo chạy trên máy người dùng — không thể vượt bằng thuật toán.

So với mô hình khoá đối xứng đã cân nhắc trước đó, thiết kế này nâng rõ rệt ngưỡng:
khoá riêng không bao giờ rời thiết bị, và lộ khoá bí mật phía server **không** đủ để
giả danh SEB Client. Biện pháp bổ sung vẫn là **code signing** (ký số binary) ở Phase 2,
là biện pháp *đáng tiền nhất* vì nó chặn được việc đóng gói lại bản đã patch.

Ngoài ra:

- Store nonce hiện là **in-memory**, chỉ đúng khi chạy **một tiến trình uvicorn**. Nếu chạy
  `--workers > 1`, client xin nonce ở worker A rồi xác thực ở worker B sẽ luôn thất bại.
- Không phải máy nào cũng có kho hệ thống (đặc biệt Linux/Wayland). Khi thiếu, client
  báo `KEYSTORE_UNAVAILABLE` và có thể chạy chế độ **giảm bảo mật** nếu GV đồng ý; hệ
  thống log `DEVICE_KEY_WEAK` để GV thấy trên dashboard. Private key **không bao giờ**
  được lưu dạng rõ.
- Client có thể tạm dừng rồi chạy tiếp: đăng nhập lại là được, không mất dữ liệu thi.
  Đây là lý do lưu trữ cục bộ được chấp nhận, nhưng cũng là điểm yếu: dữ liệu trên đĩa
  không được mã hoá phần sinh trắc.

---

## 5. Hạn chế Phase 2 (Chống crack & can thiệp mã nhị phân)

Các biện pháp bảo vệ ở Phase 2 (chống sửa đổi, chống dịch ngược và chống debug) có những giới hạn cốt lõi xuất phát từ thực tế: **phần mềm chạy trên phần cứng do người dùng kiểm soát**.

### 5.1 Giới hạn của cơ chế `self_check` (toàn vẹn nhị phân)
Cơ chế tự kiểm tra hash SHA-256 của file đang chạy so với hash nhúng sẵn mang tính chất **tự tham chiếu (self-referential)**:
- Mã thực thi tự kiểm tra nằm trong chính binary mà nó có nhiệm vụ bảo vệ.
- Kẻ tấn công có kiến thức về Reverse Engineering hoàn toàn có thể dùng debugger hoặc decompiler (Ghidra, IDA Pro, x64dbg) để tìm đoạn kiểm tra hash và sửa lệnh rẽ nhánh (VD: đổi `JZ` thành `JNZ` hoặc `NOP` toàn bộ hàm kiểm tra).
- Do đó, `self_check` chỉ có tác dụng ngăn chặn các chỉnh sửa vô tình, chỉnh sửa thô sơ (sửa file text/resource) hoặc người dùng không có kỹ năng dịch ngược; **đây là rào chắn mức đồ án, không phải giải pháp DRM thương mại**.

### 5.2 Giới hạn của cơ chế `anti_debug`
Module phát hiện debugger sử dụng các API cấp người dùng (User-mode API):
- Windows: `IsDebuggerPresent()`, `CheckRemoteDebuggerPresent()`.
- Linux: Kiểm tra `TracerPid` trong `/proc/self/status`, `ptrace(PTRACE_TRACEME)`.
- macOS: Gọi `sysctl` kiểm tra cờ `P_TRACED`.

**Giới hạn:**
- Chỉ phát hiện được các debugger tiêu chuẩn chạy ở User space (GDB, LLDB, x64dbg chế độ thường).
- **Hoàn toàn KHÔNG chống được Kernel-level debugger** (như WinDbg qua cáp COM/mạng, ScyllaHide hook ntdll, Hypervisor-based debugger, hoặc công cụ can thiệp driver như Cheat Engine DBVM).
- Khi trình bày báo cáo, **tuyệt đối không được tuyên bố hệ thống chống được dịch ngược hay chống can thiệp ở mức hạt nhân**.

### 5.3 Giới hạn của cơ chế Allowlist `client_hash`
Server lưu danh sách hash SHA-256 của các bản release hợp lệ (`signed_client_releases`) và đối chiếu khi client gửi attestation:
- **Chi phí vận hành thủ công cao:** Mỗi lần vá lỗi, cập nhật tính năng hoặc biên dịch trên một nền tảng mới (Windows, macOS, Ubuntu, Fedora), quản trị viên/giảng viên phải tính toán lại hash và đăng ký thủ công vào cơ sở dữ liệu. Nếu quên cập nhật, toàn bộ thí sinh dùng bản mới sẽ bị từ chối vào phòng thi (`CLIENT_HASH_NOT_REGISTERED`).
- **Không ngăn được việc patch runtime sau khi attestation:** Kẻ tấn công có thể để client gốc hoàn thành attestation hợp lệ để lấy token, sau đó dùng DLL Injection hoặc Memory Patching để can thiệp vào tiến trình đang chạy (VD: vô hiệu hóa `enter_kiosk()` hoặc `keyboard_guard`). Server không thể liên tục xác minh bộ nhớ động của client từ xa.

---

## 6. Hạn chế kiểm thử tải (Load Testing)

- **Chưa thử nghiệm trên cụm phân tán (Distributed Cluster):** Hệ thống mới chỉ có kịch bản kiểm thử tải dạng kịch bản mẫu/locustfile (`locustfile.py`), chạy cục bộ trên một máy đơn lẻ. Chưa có kết quả đo đạc thực tế khi chịu tải đồng thời từ hàng nghìn kết nối mạng phân tán ngoài môi trường Internet.
- **Ràng buộc tiến trình đơn (Single Worker Constraint):** Do cơ chế nonce một lần của challenge-response và bộ nhớ trạng thái WebSocket/Socket.IO hiện tại được lưu trữ in-memory trong tiến trình Python (`uvicorn app.main:app --workers 1`), hệ thống chưa thể mở rộng ngang (horizontal scale) ra nhiều worker hoặc nhiều máy chủ mà không có tầng chia sẻ trạng thái tập trung (Redis / Distributed Key-Value Store).

---

## 7. Các vấn đề kỹ thuật đã biết (Known Issues)

1. **`allow_web_fallback` chưa được cưỡng chế ở tầng backend:**
   - Cờ `allow_web_fallback = false` hiện tại chỉ được frontend đọc để hiển thị thông báo chặn trên giao diện `PolicyGate.jsx`.
   - Nếu thí sinh dùng `curl` hoặc viết script gọi thẳng `POST /api/exam-sessions/join`, backend vẫn khởi tạo phiên thi ở chế độ `restricted_mode = true` thay vì trả về `HTTP 403 SEB_REQUIRED`. Đây là quyết định chủ động ghi nhận bằng chứng thay vì chặn cứng, nhưng cần được hoàn thiện ở tầng server trong phiên bản tương lai.
2. **Sự kiện mất mạng (`CONNECTION_LOST`) và sự kiện kiểm toán bị tính gộp vào ngưỡng vi phạm:**
   - Trong `anticheat_service.py`, ngưỡng tự động nộp bài được tính bằng tổng số bản ghi trong bảng `violation_logs`.
   - Do đó, nếu mạng chập chờn kích hoạt sự kiện `CONNECTION_LOST` (mức rủi ro 5), thí sinh có thể bị mất một phần ngân sách vi phạm cho phép (`max_violation_allowed`), dù mất mạng là sự cố hạ tầng chứ không phải hành vi gian lận chủ đích.
   - Hướng xử lý: Tách biệt bộ đếm `connection_lost_count` và bộ lọc `AUDIT_ONLY_EVENT_TYPES` ra khỏi công thức tự động nộp bài `AUTO_VIOLATION`.

---

## 8. Ma trận năng lực theo hệ điều hành (lớp SEB Client — Phase 1)

| Cơ chế | Windows | macOS | Linux (X11) | Linux (Wayland) |
|---|---|---|---|---|
| Kiosk toàn màn hình | ✅ | ✅ | ✅ | ⚠️ hạn chế |
| Phát hiện cửa sổ foreground | ✅ | ✅ | ✅ | ❌ không có |
| Khoá clipboard hệ thống | ✅ | ✅ | ✅ | ⚠️ hạn chế |
| Chặn chụp màn hình | ✅ | ⚠️ hạn chế | ⚠️ hạn chế | ✅ |
| Phát hiện VM/sandbox | ✅ | ✅ | ✅ | ✅ |

> Các ô ⚠️/❌ là **giới hạn thật**, phải nêu khi trình bày. Client phải báo cáo ô trống
> qua `detail.unsupported` thay vì im lặng giả vờ đã chống được.

---

## 9. Điểm mạnh thật sự của hệ thống

Để đánh giá công bằng, các cơ chế sau **không** dễ lách, kể cả khi thí sinh cố tình:

| Điểm mạnh | Vì sao |
|---|---|
| **Đáp án đúng không bao giờ tới máy thí sinh** | `QuestionPublic` không có trường `is_correct`; kể cả đọc được toàn bộ mã nguồn cũng không biết đáp án |
| **Chấm điểm ở server** | Client không có đường nào để tự khai điểm |
| **Đồng hồ chuẩn do server giữ** | Sửa đồng hồ máy không có tác dụng; server từ chối lưu đáp án sau hạn |
| **Điểm rủi ro và log không do client quyết định** | `event_type` được whitelist, `severity` do server tính; client gửi bậy sẽ bị từ chối |
| **Chống sửa bài giả** | Kiểm tra câu hỏi có thuộc đề và lựa chọn có thuộc câu hỏi hay không |
| **Bằng chứng nguyên vẹn theo thời gian** | Mỗi vi phạm lưu cả mốc client lẫn mốc server để đối chiếu |

> Đây mới là lý do thực sự khiến việc gian lận **không đáng kể**: không phải vì bị chặn
> UI, mà vì **không có cách nào lấy đáp án và không thể tự khai điểm**.

---

## 10. Kết luận

Hệ thống đạt được mức độ phù hợp cho **bài thi trực tuyến có giám sát, kèm cơ chế phục tra**.

Nó **không** thay thế được:
- Kỷ luật phòng thi và sự hiện diện của giám thị.
- Thiết bị kiểm soát riêng do nhà trường quản lý (Lockdown Browser, Safe Exam Browser thật).
- Nhận diện khuôn mặn thời gian thực (chỉ là tuỳ chọn nâng cao, chưa triển khai).

Khi trình bày trước hội đồng, **nêu rõ mục 2 (những gì không chặn được) và mục 9 (điểm mạnh
thật sự)**. Đây là cách thể hiện sự hiểu sâu kỹ thuật, khác hẳn với việc tuyên bố
"chống gian lận 100%" — tuyên bố đó vừa sai, vừa dễ bị phát hiện là thiếu hiểu biết.
