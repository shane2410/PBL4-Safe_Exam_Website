# Đóng gói SEB Client (bản chạy thử)

Bản đóng gói là **thư mục tự chứa** (PyInstaller `onedir`): copy nguyên thư mục
sang máy khác là chạy, không cần cài Python.

## 1. Build

```bash
cd seb_client

# Linux (dùng .venv của repo)
./packaging/build.sh linux
#  → dist/SEB-Client/SEB-Client

# Windows (.exe build qua Wine + Python 3.11 trong prefix)
./packaging/build.sh windows
#  → dist-win/SEB-Client/SEB-Client.exe
```

`./packaging/build.sh` không tham số sẽ tự chọn theo hệ điều hành đang chạy.

**Vì sao không build Windows trên Linux trực tiếp:** PyInstaller không
cross-compile. Nó đóng gói thư viện của chính nền tảng đang chạy
(`QtWebEngineProcess.exe` + DLL vs `.so`), nên bản Windows phải build bằng
Python chạy trên Windows — ở đây là Python 3.11 trong prefix Wine.

**Chuẩn bị cho lần build Windows đầu tiên:**

```bash
wine "C:\\Program Files\\Python311\\python.exe" -m pip install -r \
  "$(winepath -w seb_client/requirements.txt)" "pyinstaller==6.21.0"
```

## 2. Chạy bản đóng gói

```bash
cd dist/SEB-Client        # hoặc dist-win/SEB-Client
cp .env.example .env      # rồi sửa URL backend / trang thi
./SEB-Client              # Windows: SEB-Client.exe
```

`.env`, `logs/`, `device_keys/` được đọc/ghi **cạnh file chạy**, không phải
trong `_internal/`. Nhờ vậy sửa cấu hình không cần build lại, và log không mất
khi thoát chương trình.

Cấu hình tối thiểu để trỏ về máy chủ khác:

```ini
SEB_BACKEND_URL=https://exam.truong.edu.vn
SEB_EXAM_URL_TEMPLATE=https://exam.truong.edu.vn/exam/room?room={room_code}&embedded=1
SEB_ALLOWED_ORIGINS=https://exam.truong.edu.vn
```

Sai cấu hình (thiếu `{room_code}`, template không phải http/https, danh sách
origin rỗng) thì chương trình hiện hộp thoại nêu từng lỗi kèm đường dẫn file
log rồi thoát — không có cửa sổ trắng im lặng.

## 3. Kiểm chứng bản đóng gói

| Kiểm tra | Cách làm |
|---|---|
| Nạp đúng `.env` | Log dòng `Backend:` / `Exam origin:` khớp giá trị trong `.env` |
| Ghi log ra file | `logs/seb_client_<YYYYMMDD>.log` xuất hiện cạnh file chạy |
| Năng lực OS | Dòng `Nang luc (windows): ...` liệt kê `monitor_switch` trên Windows |
| Chặn cấu hình sai | Xoá `{room_code}` khỏi `SEB_EXAM_URL_TEMPLATE` → có hộp thoại lỗi |
| QtWebEngine | Đăng nhập vào phòng thi → trang web hiển thị trong cửa sổ client |

## 4. Kích thước

Khoảng **610–660 MB/thư mục** — gần như toàn bộ là QtWebEngine (Chromium) và
các thư viện Qt đi kèm. Muốn giảm thì phải bỏ WebEngine (không còn là trình
duyệt nhúng) hoặc chuyển sang cài đặt dạng MSI dùng chung Qt runtime.
