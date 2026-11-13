"""HTTP client gọi backend FastAPI.

Hai điểm bắt buộc về bảo mật:

1. Token chỉ nằm trong RAM (`self._access_token`). Không ghi xuống
   `QSettings`, `localStorage` hay file nào.
2. `log` chỉ ghi tên endpoint, không ghi body — trong body có `password`.
"""

from __future__ import annotations

import logging

import httpx

from ..config import ClientConfig
from ..constants import (
    CLIENT_TYPE,
    CLIENT_VERSION,
    HEADER_ATTESTATION,
    HEADER_CLIENT_TYPE,
    HEADER_CLIENT_VERSION,
    HEADER_DEVICE_FINGERPRINT,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class ApiError(Exception):
    """Lỗi có cấu trúc từ backend, đủ để hiển thị cho người dùng."""

    def __init__(self, message: str, status_code: int = 0, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class ApiClient:
    """Bọc `httpx.AsyncClient` với token tự gắn vào mọi request."""

    def __init__(self, config: ClientConfig):
        self._config = config
        self._http = httpx.AsyncClient(
            base_url=config.api_root,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=False,
        )
        self._access_token: str | None = None
        self._attestation_token: str | None = None
        self._device_fingerprint: str | None = None
        self._user: dict | None = None

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    @property
    def user(self) -> dict | None:
        return self._user

    @property
    def access_token(self) -> str | None:
        """Chỉ dùng để tiêm vào web app. Xem ExamWindow._install_bootstrap_script."""
        return self._access_token

    @property
    def attestation_token(self) -> str | None:
        """Token xác thực client — gắn vào header của request do webview phát ra."""
        return self._attestation_token

    @property
    def device_fingerprint(self) -> str | None:
        return self._device_fingerprint

    def set_attestation(self, token: str | None, device_fingerprint: str | None) -> None:
        self._attestation_token = token
        self._device_fingerprint = device_fingerprint

    async def close(self) -> None:
        await self._http.aclose()
        # Dọn token khỏi RAM khi thoát.
        self._access_token = None
        self._attestation_token = None

    async def login(self, username: str, password: str) -> dict:
        """Đăng nhập và giữ token trong RAM. Trả về thông tin user."""
        payload = {"username": username.strip(), "password": password}
        try:
            response = await self._http.post(
                "/auth/login",
                json=payload,
                headers=self._base_headers(),
            )
        except httpx.HTTPError as exc:
            logger.error("Khong ket noi duoc backend tai %s: %s", self._config.backend_url, exc)
            raise ApiError(f"Không kết nối được máy chủ {self._config.backend_url}.") from exc

        if response.status_code != 200:
            raise ApiError(_friendly_message(response), response.status_code, response.text)

        data = response.json()
        self._access_token = data["access_token"]
        self._user = data.get("user")
        logger.info(
            "Dang nhap thanh cong: user=%s role=%s",
            self._user.get("username") if self._user else "?",
            ((self._user or {}).get("role") or {}).get("code", "?"),
        )
        return self._user or {}

    async def me(self) -> dict:
        self._require_auth()
        response = await self._http.get("/auth/me", headers=self._auth_headers())
        if response.status_code != 200:
            raise ApiError(_friendly_message(response), response.status_code, response.text)
        self._user = response.json()
        return self._user

    async def register_device(
        self,
        public_key: str,
        label: str | None,
        client_version: str,
        weak_key_storage: bool,
        capabilities: list[str] | None = None,
        unsupported: dict[str, str] | None = None,
    ) -> dict:
        """Đăng ký khoá công khai Ed25519 của thiết bị."""
        self._require_auth()
        response = await self._http.post(
            "/auth/client-devices",
            json={
                "public_key": public_key,
                "label": label,
                "client_version": client_version,
                "weak_key_storage": weak_key_storage,
                "capabilities": capabilities,
                "unsupported": unsupported,
            },
            headers=self._auth_headers(),
        )
        if response.status_code != 200:
            raise ApiError(_friendly_message(response), response.status_code, response.text)
        return response.json()

    async def client_nonce(self) -> dict:
        """Xin nonce 1-lần để ký."""
        self._require_auth()
        response = await self._http.post(
            "/auth/client-nonce", json={}, headers=self._auth_headers()
        )
        if response.status_code != 200:
            raise ApiError(_friendly_message(response), response.status_code, response.text)
        return response.json()

    async def client_attest(
        self,
        nonce: str,
        client_version: str,
        device_fingerprint: str,
        signature: str,
        device_id: str,
    ) -> dict:
        """Gửi chữ ký Ed25519 để chứng minh là SEB Client thật."""
        self._require_auth()
        response = await self._http.post(
            "/auth/client-attest",
            json={
                "nonce": nonce,
                "client_version": client_version,
                "device_fingerprint": device_fingerprint,
                "signature": signature,
                "device_id": device_id,
            },
            headers=self._auth_headers(),
        )
        if response.status_code != 200:
            raise ApiError(_friendly_message(response), response.status_code, response.text)
        return response.json()

    async def join_exam(self, room_code: str) -> dict:
        """Vào phòng thi bằng mã phòng, trả về đề + policy đã resolve.

        Response KHÔNG chứa `is_correct` — đáp án nằm ở backend, chấm ở server.
        """
        self._require_auth()
        response = await self._http.post(
            "/exam-sessions/join",
            json={"room_code": room_code.strip().upper(), "client_type": CLIENT_TYPE},
            headers=self._auth_headers(),
        )
        if response.status_code != 200:
            raise ApiError(_friendly_message(response), response.status_code, response.text)

        data = response.json()
        logger.info(
            "Vao phong %s: session=%s, %d cau, restricted_mode=%s",
            room_code,
            data.get("session_token", "?")[:8],
            len(data.get("questions") or []),
            data.get("restricted_mode"),
        )
        if data.get("restricted_mode"):
            logger.warning(
                "Phien thi dang o restricted_mode — client chua duoc xac thuc day du"
            )
        return data

    async def submit_exam(self, session_token: str, submit_type: str = "AUTO_TIMEOUT") -> dict:
        """Chủ động nộp bài lên server.

        Tại sao client phải tự gọi: khi hết giờ, `ExamWindow` ẩn `web_view` để
        hiện màn hình chặn. Trang React bên trong không còn cơ hội gửi POST nộp
        bài, nên nếu chỉ dựa vào web app thì phiên thi sẽ kẹt IN_PROGRESS và
        không bao giờ được chấm điểm.

        Idempotent ở phía server: nộp lại phiên đã SUBMITTED trả về kết quả cũ.
        """
        self._require_auth()
        response = await self._http.post(
            "/exam-sessions/submit",
            json={"submit_type": submit_type, "session_token": session_token},
            headers=self._auth_headers(),
        )
        if response.status_code != 200:
            raise ApiError(_friendly_message(response), response.status_code, response.text)
        data = response.json()
        logger.info(
            "Da nop bai (type=%s): session=%s score=%s",
            submit_type, session_token[:8], data.get("final_score"),
        )
        return data

    def _require_auth(self) -> None:
        if not self._access_token:
            raise ApiError("Chưa đăng nhập.")

    def _base_headers(self) -> dict[str, str]:
        return {
            HEADER_CLIENT_TYPE: CLIENT_TYPE,
            HEADER_CLIENT_VERSION: CLIENT_VERSION,
        }

    def _auth_headers(self) -> dict[str, str]:
        headers = self._base_headers()
        headers["Authorization"] = f"Bearer {self._access_token}"
        if self._attestation_token:
            headers[HEADER_ATTESTATION] = self._attestation_token
        if self._device_fingerprint:
            headers[HEADER_DEVICE_FINGERPRINT] = self._device_fingerprint
        return headers


def _friendly_message(response: httpx.Response) -> str:
    """Rút thông điệp có thể hiện cho người dùng từ response của FastAPI."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        return f"Máy chủ trả về lỗi {response.status_code}."

    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            return str(first.get("msg", f"Máy chủ trả về lỗi {response.status_code}."))
    return f"Máy chủ trả về lỗi {response.status_code}."