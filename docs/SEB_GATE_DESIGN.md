# Thiết kế: Cơ chế bắt buộc thi qua Safe Exam Browser Client

> Tài liệu thiết kế cho **cổng bắt buộc SEB** (cờ `only through safe exam browser`).
> Bổ sung cho `docs/PLAN.md` mục 0 — phần ở đó chỉ nêu *ý định*, chưa có đặc tả.
>
> **Nguyên tắc trung thực (Quy tắc #5):** tài liệu này mô tả điều hệ thống *bảo đảm*
> và điều hệ thống *không bảo đảm*. Mọi phần đã triển khai đều đánh dấu trạng thái
> để không nhầm "đã có" với "đang định nghĩa".

---

## 1. Mục tiêu và ranh giới

### 1.1 Hệ thống **bảo đảm**

| # | Bảo đảm | Cách thực hiện |
|---|---|---|
| G1 | Đáp án đúng không bao giờ tới client | `QuestionPublic` không có `is_correct`; chấm điểm ở server |
| G2 | Cấu hình đề không nằm trong binary client | Client tải `security_policy` từ server mỗi lần vào phòng |
| G3 | Chấm điểm và quyết định nộp bài ở server | Client chỉ nhận lệnh, không có đường tự khai điểm |
| G4 | Phân biệt được phiên thi có và không qua xác thực | `attestation_status` ∈ {VERIFIED, NOT_ATTESTED, REQUIRED_MISSING} |
| G5 | Một tài khoản chỉ có một phiên socket tại một thời điểm | `DUPLICATE_LOGIN` kick kết nối cũ (server-side, không bypass được) |
| G6 | Đồng hồ chuẩn do server giữ | `server_time` + `deadline`; client sửa đồng hồ máy không ảnh hưởng |

### 1.2 Hệ thống **KHÔNG bảo đảm** (phải nêu trong báo cáo)

- **Một SEB Client đã crack không thể bị chặn.** Mọi guard ở Phase 1 chạy trên máy
  thí sinh. Biên dịch C++ (mục 8) chỉ làm tăng chi phí decompile, **không** làm guard
  trở nên đáng tin.
- **Vi phạm do client báo không phải bằng chứng.** Xem mục 7.
- **Không chặn được thiết bị thứ hai, camera, phần mềm ghi màn hình ở tầng OS.**
  Xem `docs/BAOCAO_LIMITATION.md`.

---

## 2. Quy tắc hiệu lực

```
seb_required = (exam.require_safe_browser == true)
              AND (system_settings.require_safe_browser_global == true)
```

- Hai cờ đều đọc qua `ExamSecurityService.is_safe_browser_required()` — nguồn sự
  thật duy nhất, dùng chung cho web lẫp SEB.
- GV được **tắt** yêu cầu cho từng đề kể cả khi cờ hệ thống đang bật, để tránh một
  đề bất thường chặn cả lớp.

### 2.1 `allow_web_fallback` — cần sửa (hiện chưa được thi hành)

`allow_web_fallback` **hiện chỉ được frontend đọc** (`PolicyGate.jsx`,
`ExamRoom.jsx`). Backend không kiểm tra ở bất kỳ đâu. Hệ quả: cổng "bắt buộc SEB"
nằm trong trình duyệt của thí sinh — gọi thẳng `POST /exam-sessions/join` bằng
`curl` là qua.

**Thiết kế mong muốn** (thuộc phần sửa web, không làm trong Phase 1):

```
seb_required == true
  AND identity.attested == false
  AND policy.allow_web_fallback == false
    → HTTP 403 SEB_REQUIRED, KHÔNG tạo phiên
```

Cho tới khi sửa, tài liệu phải mô tả đúng là: web fallback **không bị chặn ở tầng
server**, chỉ được khuyến nghị ở tầng giao diện.

---

## 3. Máy trạng thái phiên thi

```
                  vào phòng
                     │
      ┌──────────────┴──────────────┐
      │                             │
 NOT_ATTESTED /                 attested = true
 REQUIRED_MISSING                      │
      │                             VERIFIED
      │  (web, restricted_mode=true)    │
      └──────────────┬──────────────┬───┘
                     │              │
              RESTRICTED ──────────┤
                     │              │
                     └──────┬───────┘
                            │
                      IN_PROGRESS
                     │          │
            SUBMITTED      force_submit (vượt ngưỡng)
```

Quy tắc:

| Trạng thái | Được gọi API nào | Ghi chú |
|---|---|---|
| `NOT_ATTESTED` | join, save-answer, submit | Đề không bắt buộc SEB |
| `REQUIRED_MISSING` | như trên + ghi `UNAUTHORIZED_CLIENT` | Đề bắt buộc SEB nhưng web vẫn vào được (xem 2.1) |
| `VERIFIED` | đầy đủ, heartbeat có kiểm tra chữ ký | Chế độ đầy đủ ràng buộc |
| `SUBMITTED` | chỉ đọc kết quả | Mọi ghi bị từ chối |

**Cần bổ sung trong backend:** hiện `ExamSession.status` chỉ có `IN_PROGRESS` /
`SUBMITTED` / `DISCONNECTED`. Trạng thái xác thực đang nằm ở cột riêng
`attestation_status` + `restricted_mode` trả về cho client, **không** được dùng để
chặn request. Nên xem xét thêm một dependency chặn theo trạng thái khi Phase 1
làm xong.

---

## 4. Hợp đồng API

Tất cả endpoint `/api`.

### 4.0 `POST /auth/client-devices` *(mới — mô hình Ed25519)*

| | |
|---|---|
| Header | `Authorization: Bearer <access_token>` |
| Request | `{ "public_key": "<base64 Ed25519 raw 32 bytes>", "label": "..." }` |
| Response 200 | `{ "device_id": "a1b2c3d4e5f60718", "already_registered": true }` |

`device_id = sha256(public_key)[:16]`. Gọi lại với cùng public key trả
`already_registered = true` — cho phép client khôi phục mà không tạo bản ghi rác.
Key lạ chưa từng đăng ký thì tạo mới và **log `DEVICE_REGISTERED`**.

---

### 4.1 `POST /auth/client-nonce`

Sinh nonce dùng một lần, TTL 30 giây.

| | |
|---|---|
| Header bắt buộc | `Authorization: Bearer <access_token>` |
| Request | *(không body)* |
| Response 200 | `{ "nonce": "...", "ttl_seconds": 30 }` |
| Response 401 | Token đăng nhập hết hạn |

**Ghi chú triển khai:** nonce lưu trong RAM (`_pending_nonces`). Hệ thống phải chạy
**1 worker**; restart là mất toàn bộ nonce đang chờ (chấp nhận được, TTL chỉ 30 s).

### 4.2 `POST /auth/client-attest`

| | |
|---|---|
| Request | `{ "nonce", "client_version", "device_fingerprint", "signature" }` |
| `signature` | `base64(Ed25519_sign(private_key, f"{nonce}\|{client_version}\|{device_fingerprint}\|{device_id}"))` |
| Response 200 | `{ "attested": true, "device_id": "...", "attestation_token": "...", "verification_reason": null }` |
| Response 200 (fail) | `{ "attested": false, "verification_reason": "NONCE_INVALID_OR_EXPIRED" }` |

Server xác minh chữ ký Ed25519 bằng **public key đã đăng ký của `device_id`**.
Nonce bị xoá khỏi bộ nhớ **ngay khi kiểm tra**, kể cả khi hỏng — chống replay.

> **Hiện trạng (Phase 0):** backend đang chạy mô hình khoá đối xứng cũ
> (`HMAC(device_secret, ...)` với `compare_digest`). Mô hình Ed25519 ở trên là thay
> thế cho nó ở Phase 1 — xem `docs/PLAN.md` mục 1.5.2 và bảng hạng mục ở mục 8.

`verification_reason` có thể trả về: `NONCE_INVALID_OR_EXPIRED`, `NONCE_EXPIRED`,
`NONCE_USER_MISMATCH`, `SIGNATURE_MISMATCH`.

### 4.3 `POST /exam-sessions/join`

| | |
|---|---|
| Header | `X-Client-Type: web\|seb`, `X-Client-Version`, `X-Device-Fingerprint`, `X-Attestation-Token` |
| Request | `{ "room_code", "client_type" }` |
| Response 200 | `{ "session_token", "questions", "security_policy", "require_safe_browser", "restricted_mode", "server_time", "remaining_seconds" }` |

**Header `X-Client-Type` là do client tự khai — không phải bằng chứng.** Server chỉ
chấp nhận `attested = true` khi `X-Attestation-Token` xác minh được. Giá trị rác →
mặc định an toàn về `web`.

### 4.4 `GET /exam-sessions/{session_token}/identity`

Trả `attestation_status` hiện tại — SEB Client dùng để biết mình đang ở chế độ nào.

### 4.5 Mã lỗi cần chốt (hiện chưa có)

| Mã | Ý nghĩa | Khi nào trả |
|---|---|---|
| `403 SEB_REQUIRED` | Đề bắt buộc SEB, client không xác thực được, và `allow_web_fallback=false` | Mục 2.1 |
| `401 ATTESTATION_TOKEN_INVALID` | Token xác thực hết hạn hoặc sai fingerprint | Mọi endpoint nhạy cảm |
| `409 CLIENT_VERSION_TOO_OLD` | `client_version` < `seb_client_config.min_version` | `join`, `attest` |
| `422 CLIENT_HASH_UNKNOWN` | Hash client không nằm trong `signed_client_releases` | `join` (Phase 2) |

---

## 5. Vòng đời xác thực

```
1. POST /auth/login                      → access_token
2. Sinh/đọc cặp khoá Ed25519 (lần đầu: lưu private key vào kho hệ thống)
3. POST /auth/client-devices             → device_id
4. POST /auth/client-nonce               → nonce (TTL 30 s)
5. Ký: Ed25519(f"{nonce}|{ver}|{fp}|{device_id}") bằng private key
6. POST /auth/client-attest              → attestation_token + device_id
7. Mọi request kèm X-Attestation-Token (TTL 5 phút)
8. Heartbeat ký bằng CÙNG private key đó: Ed25519(f"{session_id}|{server_nonce}")
8. Socket.IO: join_exam_room, heartbeat
```

### 5.1 Khoá xác thực — Ed25519 sinh trên máy (đã chốt)

> **Thiết kế chi tiết và đầy đủ nằm ở `docs/PLAN.md` mục 1.5.2.** Tóm tắt ở đây.

Mô hình ban đầu dùng `device_secret = HMAC(SECRET_KEY, salt)` — khoá đối xứng do
server sinh ra. Điều đó tạo ra mâu thuẫn không giải quyết được: client cần khoá để
ký, nhưng `SECRET_KEY` không được gửi xuống client.

**Đã chốt:** chuyển sang cặp khoá **bất đối xứng Ed25519 sinh ngay trên thiết bị**.

```
private key -> kho hệ thống (DPAPI / Keychain / Secret Service)
public key  -> đăng ký lên server, lưu bảng client_devices
device_id   -> sha256(public_key)[:16]
```

Hai hệ quả làm cho thiết kế này vượt hẳn mô hình cũ:

1. **Server không thể tự dựng khoá giả.** Với HMAC, server giữ khoá nên về lý thuyết
   nó có thể ký thay client. Với Ed25519, server chỉ có public key — không tạo được
   chữ ký hợp lệ.
2. **Lộ `SECRET_KEY` không còn đủ để giả attestation.** Phải có private key trên đúng
   thiết bị đó. Nên hàng **C13** trong bảng mô hình đe doạ hạ từ *Cao* xuống *Trung
   bình* — vẫn nghiêm trọng (mất JWT) nhưng không còn là điều kiện tiên quyết.

#### Hệ quả đối với các hạng mục đã liệt kê

Hạng mục 1 và 2 trong mục 8 (đổi `SECRET_KEY`, bắt buộc `device_secret_salt` cho mọi
user) **không còn đúng nữa** và cần thay bằng:

| # | Hạng mục mới | Nơi sửa |
|---|---|---|
| 1 | Bảng `client_devices` + migration | `models/` |
| 2 | `POST /auth/client-devices` (đăng ký / lấy lại public key) | `routers/auth_router.py` |
| 3 | `verify_attestation` dùng Ed25519 thay HMAC | `services/attestation_service.py` |
| 4 | `exam_sessions` thêm `device_id` | migration |
| 5 | Bỏ `device_secret_salt` khỏi luồng attest (giữ cột để tương thích nếu cần) | `services/attestation_service.py` |
| 6 | `X-Device-Fingerprint` = hash public key, bỏ MAC/hostname | `dependencies/client_identity.py` |

#### Rủi ro mới do mô hình này mang lại

| Rủi ro | Xử lý |
|---|---|
| Máy không có kho hệ thống (đặc biệt Linux/Wayland) | Client báo `KEYSTORE_UNAVAILABLE`; GV quyết định có cho chạy chế độ giảm bảo mật không. **Không bao giờ** lưu private key dạng rõ |
| Thí sinh cài lại máy → mất khoá | Đăng ký lại được, nhưng **phải log** `DEVICE_RE_REGISTERED` — sự kiện này bất thường và đáng ngờ |
| Máy tính dùng chung nhiều thí sinh | Mỗi `(user_id, device_id)` là một cặp riêng; giới hạn số thiết bị / tài khoản theo cấu hình GV |
| Private key bị trích từ máy đã bị chiếm quyền | Vẫn xảy ra — nhưng cần chiếm quyền ở mức hệ điều hành, cao hơn hẳn mức chạy script Python |

### 5.2 Heartbeat — chưa được xác minh chữ ký

`exam_namespace.heartbeat()` hiện **chỉ ghi lại mốc thời gian**, không kiểm tra chữ
ký nào. Plan mục 2.3.1 mô tả `heartbeat.py` ký HMAC bằng `attestation_key` — phần
này **chưa có trong backend**.

Cần làm (thuộc Phase 1):

- Client gửi kèm `attestation_key`-derived HMAC trong mỗi heartbeat.
- Server xác minh trước khi cập nhật `last_heartbeat`.
- Heartbeat sai chữ ký → không cập nhật mốc → sau 30 s bị đánh `DISCONNECTED` như
  hiện tại, **và** ghi `violation` loại mới.

---

## 6. `attestation_status` và giá trị của bằng chứng

| Giá trị | Nghĩa | Bằng chứng vi phạm có giá trị? |
|---|---|---|
| `VERIFIED` | Challenge-response thành công | ✅ Có — có thể dùng làm căn cứ |
| `NOT_ATTESTED` | Đề không bắt buộc SEB | ⚠️ Có, kèm chú thích "phiên không xác thực" |
| `REQUIRED_MISSING` | Đề bắt buộc SEB nhưng client không attest | ❌ **Không** — chỉ để *gợi nghi*, tuyệt đối không làm căn cứ kỷ luật |

**Quy tắc bắt buộc:** mọi truy vấn vi phạm phải kèm `attestation_status`. Báo cáo
phải hiển thị cột này. Nếu không, hệ thống sẽ kết tội một thí sinh chỉ vì bịa ra
tín hiệu bằng chứng từ máy đã bị can thiệp.

---

## 7. Quy trình khi bị từ chối

Thí sinh dùng web mà đề bắt buộc SEB:

1. Màn `PolicyGate` hiện hướng dẫn tải client, kèm 3 nút theo OS.
2. Nếu GV cho phép fallback: hiện nút "Thi bằng trình duyệt ở chế độ hạn chế".
3. **Nút tải client hiện là placeholder** (chưa nối URL thật — Phase 1).
4. Nếu không cho fallback: phải trả `403 SEB_REQUIRED` ở server (mục 2.1).

GV nhìn thấy trên dashboard giám sát:

- Cột `attestation_status` cho từng phiên.
- Sự kiện `UNAUTHORIZED_CLIENT` khi phiên `REQUIRED_MISSING` được tạo.

---

## 8. Phần còn thiếu cần bổ sung

| # | Hạng mục | Nơi sửa | Phase |
|---|---|---|---|
| 0 | **Chốt cách client lấy khoá xác thực** (a/b/c) | xem `docs/PLAN.md` mục 1.5.2 | **trước mọi thứ** |
| 1 | `SECRET_KEY` bắt buộc từ biến môi trường, chết nếu còn giá trị mặc định | `app/core/config.py` | 1 |
| 2 | Sinh `device_secret_salt` cho **mọi** user, chặn khi salt rỗng | `seed_data.py`, `attestation_service.py` | 1 |
| 3 | Thi hành `allow_web_fallback` → `403 SEB_REQUIRED` | `exam_session_service.join_exam` | sau SEB |
| 4 | Xác minh HMAC heartbeat | `exam_namespace.heartbeat` | 1 |
| 5 | Bảng `client_attestations` | migration | 1 |
| 6 | Mã lỗi mục 4.5 | `app/schemas/`, `app/api/routers/` | 1 |
| 7 | Cột `attestation_status` trong mọi báo cáo vi phạm | `report_router.py`, `MonitorDashboard.jsx` | 1 |
| 8 | `device_fingerprint` vào `exam_sessions` + giới hạn số thiết bị | migration | 2 |
| 9 | `client_hash` đối chiếu `signed_client_releases` | `join_exam` | 2 |
| 10 | Quy trình khiếu nại khi bị tự nộp oan | `docs/` + UI GV | 2 |
| 11 | Đối chiếu cấu hình client (`config_version` + hash) | xem `docs/SEB_CLIENT_SPEC.md` | 1 |
| 12 | Mật khẩu giám thị để thoát phòng thi | xem `docs/SEB_CLIENT_SPEC.md` | 1 |

---

## 9. Quy trình kiểm thử cổng

| # | Bước | Kết quả mong đợi |
|---|---|---|
| T1 | Web client, đề **không** bắt buộc SEB | Vào được, `NOT_ATTESTED` |
| T2 | Web client, đề bắt buộc SEB, fallback bật | Vào được, `REQUIRED_MISSING`, hiện `PolicyGate` |
| T3 | Web client, đề bắt buộc SEB, fallback tắt | `403 SEB_REQUIRED` *(chưa triển khai — mục 2.1)* |
| T4 | `curl` khai `X-Client-Type: seb` không có token | Vẫn là `web`, `attested=false` |
| T5 | Nonce dùng 2 lần | Lần 2 `NONCE_INVALID_OR_EXPIRED` |
| T6 | Nonce cũ hơn 30 s | `NONCE_EXPIRED` |
| T7 | Sửa 1 byte chữ ký | `SIGNATURE_MISMATCH` |
| T8 | Token xác thực dùng lại sang fingerprint khác | `attested=false`, phiên rơi về `REQUIRED_MISSING` *(chưa trả 401 — xem mục 8 #6)* |
| T9 | Client thật, đúng quy trình | `VERIFIED`, heartbeat giữ liên tục |
| T10 | Ngắt mạng 30 s | `DISCONNECTED` + `CONNECTION_LOST` |

T1–T2, T4–T7, T10 chạy được với backend hiện tại. **T3 chưa triển khai** (mục 2.1),
**T8 trả về `attested=false` chứ chưa phải `401`** — cần bổ sung mã lỗi ở mục 4.5.