"""Gắn định danh client vào mọi request do webview phát ra.

Vì sao cần: trang web thi chạy **bên trong** `QWebEngineView` gọi API bằng
JavaScript/axios. Những request đó không đi qua `ApiClient` (httpx) nên không
có header `X-Client-Type`, `X-Attestation-Token`, `X-Device-Fingerprint`.

Hệ quả nếu thiếu: server coi request là của trình duyệt thường, trả
`restricted_mode = true` cho chính phiên đã xác thực SEB. Thí sinh đang dùng
đúng client vẫn thấy màn hình "Đề thi này yêu cầu Safe Exam Browser", và mỗi
lần join cộng oan `UNAUTHORIZED_CLIENT` vào risk score.

Nguyên tắc bảo mật: **chỉ gắn header vào origin đã được cho phép**. Attestation
token là thông tin xác thực; gửi kèm khi webview tải ảnh/CDN/nội dung bên thứ
ba nghĩa là làm rò rỉ token ra ngoài.
"""

from __future__ import annotations

import logging
from typing import Callable, Iterable
from urllib.parse import urlparse

from PySide6.QtWebEngineCore import QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor

logger = logging.getLogger(__name__)

_WELL_KNOWN_PORTS = {"http": 80, "https": 443}


def _origin_key(url: str) -> str | None:
    """Chuẩn hoá URL thành `scheme://host:port` để so khớp origin."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if not scheme or not host:
        return None
    port = parsed.port or _WELL_KNOWN_PORTS.get(scheme, 0)
    if port <= 0:
        return None
    return f"{scheme}://{host}:{port}"


class ClientIdentityInterceptor(QWebEngineUrlRequestInterceptor):
    """Thêm header định danh client vào request thuộc origin tin cậy.

    `header_provider` được gọi tại thời điểm request, không phải lúc khởi tạo:
    attestation token có TTL 5 phút và được làm mới sau khi attest lại, nên giữ
    giá trị cũ sẽ khiến mọi request sau đó bị từ chối.
    """

    def __init__(
        self,
        header_provider: Callable[[], dict[str, str]],
        allowed_origins: Iterable[str],
        parent=None,
    ):
        super().__init__(parent)
        self._header_provider = header_provider
        self._allowed = {key for origin in allowed_origins if (key := _origin_key(origin))}
        self._injected = 0
        logger.info(
            "Interceptor dinh danh: chi gan header cho %d origin",
            len(self._allowed),
        )

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        """Qt gọi hàm này cho MỌI request — phải rẻ và không bao giờ ném lỗi."""
        try:
            key = _origin_key(info.requestUrl().toString())
            if key is None or key not in self._allowed:
                return
            headers = self._header_provider()
            if not headers:
                return
            for name, value in headers.items():
                if value:
                    info.setHttpHeader(name.encode("latin-1"), value.encode("latin-1"))
            self._injected += 1
        except Exception as exc:  # noqa: BLE001 - lỗi ở đây sẽ chặn request
            logger.warning("Khong gan duoc header dinh danh: %s", exc)

    @property
    def injected_count(self) -> int:
        return self._injected
