# Mở bằng file cấu hình `.seb`

Đây là mô hình của Safe Exam Browser thật: giảng viên phát hành **một file cấu
hình**, thí sinh mở file đó, và client khởi động thành trình duyệt bị khoá đúng
theo cấu hình ấy.

## 1. Hai chế độ chạy

| | Chế độ thi (có backend) | Chế độ file `.seb` |
|---|---|---|
| Khởi động | Chạy `SEB-Client` không đối số | Mở file `.seb` / `SEB-Client exam.seb` |
| Đăng nhập | Bắt buộc | Không |
| Vào phòng | `join_exam` + socket + heartbeat | Không |
| Trang mở | `SEB_EXAM_URL_TEMPLATE` trong `.env` | `startURL` trong file `.seb` |
| Khoá an toàn | Theo policy server trả về | Theo khoá trong file `.seb` |
| Giám sát / đếm vi phạm | Có, ghi lên dashboard | Không — chỉ ghi log |
| Tự nộp khi hết giờ | Có | Không |

Chế độ file cấu hình **không thay thế** chế độ thi. Nó dùng khi:
- muốn thử cơ chế khoá trước khi nối backend,
- phát hành kỳ thi không cần giám sát realtime,
- mở một trang web bất kỳ trong môi trường bị khoá.

## 2. Mở file `.seb`

```bash
# Linux
./SEB-Client "exam-pbl4.seb"

# Windows: double-click file .seb → chọn SEB-Client,
# hoặc gán file .seb cho SEB-Client.exe để lần sau chỉ cần double-click.
SEB-Client.exe "exam-pbl4.seb"
```

Trên Windows, để double-click là mở được: chuột phải file `.seb` → **Open
with** → **Choose another app** → trỏ tới `SEB-Client.exe` → tick *Always use
this app*.

## 3. File `.seb` đọc được những gì

Định dạng là **plist XML** — cùng định dạng SEB chính thức xuất ra, nên file do
SEB Config Tool tạo cũng đọc được.

| Khoá `.seb` | Tác dụng trong client |
|---|---|
| `startURL` / `startUrl` | Trang mở đầu tiên (bắt buộc) |
| `allowPrint` | `false` → chặn in |
| `clipboardPolicy` | `1` → chặn copy/paste; `0`/`2` → cho phép |
| `enableRightMouse` | `false` → chặn menu chuột phải |
| `allowDeveloperConsole` | `false` → chặn DevTools |
| `browserWindowAllowAddressBar` | `false` → không hiện thanh địa chỉ |
| `browserWindowAllowReload` | `false` → chặn tải lại trang |
| `enableAltTab` | `false` → chặn Alt+Tab |
| `enableEsc`, `enableCtrlEsc` | `false` → chặn Esc / Ctrl+Esc |
| `enablePrintScreen` | `false` → chặn PrintScreen |
| `blockPopUpWindows` | `true` → chặn cửa sổ bật lên |
| `allowQuit` | `false` → không cho thí sinh tự thoát |
| `hashedQuitPassword` | Hash mật khẩu giám thị (chưa dùng để mở khoá — xem mục 5) |
| `whitelistURLFilter` | Danh sách origin được phép nạp thêm |
| `URLFilterRules` | Rule có `expression` dạng URL đầy đủ → thêm vào origin cho phép |

Khoá nào client **chưa** làm được (lọc URL bằng regex, `killExplorerShell`,
`monitorProcesses`, `browserExamKey`, `sebServerURL`…) sẽ hiện trong hộp thoại
"cấu hình có phần chưa hỗ trợ" **và** ghi log — không im lặng bỏ qua.

## 4. Tạo file `.seb`

Có sẵn công cụ, không phải viết plist tay:

```bash
# Mặc định: khoá chặt (không in, không copy, không DevTools, chặn Alt+Tab)
python -m sebclient.make_seb \
    --url "http://localhost:5173/exam/room?room=PBL4-EXAM-01" \
    --allow-origin http://127.0.0.1:8000 \
    --out exam-pbl4.seb

# Nới lỏng: cho in và copy/paste
python -m sebclient.make_seb \
    --url "https://exam.truong.edu.vn/room/PBL4-EXAM-01" \
    --allow-print --allow-copy \
    --out exam-pbl4.seb
```

`--allow-origin` lặp lại được, mỗi lần thêm một origin — cần khi trang thi gọi
API ở origin khác (ví dụ backend `127.0.0.1:8000`).

Tham số đầy đủ: `python -m sebclient.make_seb --help`

## 5. Giới hạn phải nói rõ

- **Không giám sát được.** Không có backend nghĩa là không có dashboard, không
  đếm vi phạm, không cưỡng chế thu bài. Sự kiện chỉ nằm trong log máy thí sinh.
- **Không tự nộp khi hết giờ.** File `.seb` không chứa thời lượng thi.
- **`hashedQuitPassword` chưa dùng để mở khoá thoát.** Client đọc và ghi log,
  nhưng chưa có hộp thoại nhập mật khẩu giám thị. Nếu `allowQuit=false` mà không
  có mật khẩu, client vẫn cho đóng cửa sổ để tránh kẹt cứng — đây là lựa chọn có
  chủ ý, và có cảnh báo trong log.
- **Chặn DevTools/Ctrl+P ở tầng Qt, không phải tầng OS.** Thí sinh dùng công cụ
  bên ngoài (AutoHotkey, macro) vẫn có thể gửi tổ hợp phím tới cửa sổ khác —
  như mọi trình duyệt nhúng.
- **`startURL` phải là `http://` hoặc `https://`.** File trỏ tới `file://` bị
  từ chối: mở file cục bộ trong cửa sổ "khoá" là bề mặt tấn công, không phải
  tính năng.

## 6. Định dạng file tối thiểu

Client chỉ cần `startURL`; mọi khoá khác có mặc định thiên về an toàn:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>startURL</key>
    <string>http://localhost:5173/exam/room?room=PBL4-EXAM-01</string>
</dict>
</plist>
```
