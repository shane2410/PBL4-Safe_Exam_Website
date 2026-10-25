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

## 5. Ma trận năng lực theo hệ điều hành (lớp SEB Client — Phase 1)

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

## 6. Điểm mạnh thật sự của hệ thống

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

## 7. Kết luận

Hệ thống đạt được mức độ phù hợp cho **bài thi trực tuyến có giám sát, kèm cơ chế phục tra**.

Nó **không** thay thế được:
- Kỷ luật phòng thi và sự hiện diện của giám thị.
- Thiết bị kiểm soát riêng do nhà trường quản lý (Lockdown Browser, Safe Exam Browser thật).
- Nhận diện khuôn mặn thời gian thực (chỉ là tuỳ chọn nâng cao, chưa triển khai).

Khi trình bày trước hội đồng, **nêu rõ mục 2 (những gì không chặn được) và mục 6 (điểm mạnh
thật sự)**. Đây là cách thể hiện sự hiểu sâu kỹ thuật, khác hẳn với việc tuyên bố
"chống gian lận 100%" — tuyên bố đó vừa sai, vừa dễ bị phát hiện là thiếu hiểu biết.
