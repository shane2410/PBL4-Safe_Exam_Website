"""Test phần khoá thiết bị và xác thực Ed25519.

Hai thứ phải khớp CHÍNH XÁC với backend, sai một ký tự là chữ ký hỏng:
  - công thức `build_attest_message`
  - công thức `device_id` / `fingerprint`
Nên chúng được test thuần, không cần Qt lẫn mạng.
"""

import base64
import hashlib

import pytest

from sebclient.api.attestation import build_attest_message
from sebclient.config import ClientConfig
from sebclient.osint.keystore import DeviceKey

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _make_key() -> DeviceKey:
    private_key = Ed25519PrivateKey.generate()
    public_b64 = base64.b64encode(
        private_key.public_key().public_bytes_raw()
    ).decode()
    return DeviceKey(
        private_key=private_key, public_key_b64=public_b64, weak_storage=False
    )


def test_device_id_derived_from_public_key():
    key = _make_key()
    raw = base64.b64decode(key.public_key_b64)
    expected = hashlib.sha256(raw).hexdigest()[:16]
    assert key.device_id == expected
    assert len(key.device_id) == 16


def test_fingerprint_is_prefix_of_device_id():
    """device_id phải là 16 ký tự đầu của fingerprint — backend suy ra device_id
    từ fingerprint trong header, nếu lệch thì ghi sai cột."""
    key = _make_key()
    assert key.fingerprint.startswith(key.device_id)
    assert len(key.fingerprint) == 64


def test_signature_verifies_with_public_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    key = _make_key()
    message = b"nonce|1.0.0|fp|devid"
    signature = base64.b64decode(key.sign(message))
    Ed25519PublicKey.from_public_bytes(
        base64.b64decode(key.public_key_b64)
    ).verify(signature, message)


def test_attest_message_format():
    """Công thức này phải khớp `build_attest_message` ở backend
    (app/services/attestation_service.py). Đây là hợp đồng, không phải chi tiết
    triển khai — đổi một dấu gạch là toàn bộ client không attest được."""
    message = build_attest_message("NONCE123", "1.0.0", "FP456", "DEV789")
    assert message == b"NONCE123|1.0.0|FP456|DEV789"
    assert message.count(b"|") == 3


def test_attest_message_is_deterministic():
    a = build_attest_message("n", "v", "f", "d")
    b = build_attest_message("n", "v", "f", "d")
    assert a == b


def test_keystore_never_writes_plaintext_private_key(tmp_path):
    """Hồi quy bảo mật.

    Bản đầu tiên của keystore lưu private key dạng base64 rõ trong JSON, vi phạm
    đúng nguyên tắc module đó tuyên bố. Test này chặn tái phát.
    """
    from sebclient.osint.keystore import load_or_create

    key_dir = tmp_path / "keys"
    load_or_create(key_dir)

    for path in key_dir.glob("*"):
        if path.suffix != ".json":
            continue
        content = path.read_text(encoding="utf-8")
        assert "private_key" not in content, (
            f"{path.name} đang chứa private key dạng rõ — phải mã hoá bằng kho hệ thống"
        )


# ------------------------------------------------------------------- config


def test_config_builds_exam_url_from_template():
    config = ClientConfig(
        exam_url_template="http://10.0.0.5:5173/exam/room?room={room_code}&embedded=1"
    )
    assert config.build_exam_url("PBL4-01") == (
        "http://10.0.0.5:5173/exam/room?room=PBL4-01&embedded=1"
    )


def test_config_rejects_template_without_room_code():
    config = ClientConfig(exam_url_template="http://x/exam")
    problems = config.validate()
    assert any("room_code" in p for p in problems)


@pytest.mark.parametrize(
    "template", ["file:///etc/passwd", "javascript:alert(1)", "ftp://host/x"]
)
def test_config_rejects_non_http_scheme(template):
    config = ClientConfig(exam_url_template=template + "?room={room_code}")
    problems = config.validate()
    assert any("http" in p for p in problems)


def test_config_rejects_empty_allowed_origins():
    config = ClientConfig(allowed_origins=())
    problems = config.validate()
    assert any("ALLOWED_ORIGINS" in p for p in problems)


def test_default_template_carries_embedded_flag():
    """`embedded=1` là bắt buộc: thiếu nó thì web app tự mở socket thứ hai và
    server ghi DUPLICATE_LOGIN rồi buộc nộp bài — tức dùng đúng SEB thì bị phạt."""
    config = ClientConfig()
    assert "embedded=1" in config.exam_url_template
def test_deployed_origins_are_used_when_overrides_are_unset(monkeypatch):
    from sebclient.config import ClientConfig

    monkeypatch.delenv("SEB_EXAM_URL_TEMPLATE", raising=False)
    monkeypatch.delenv("SEB_ALLOWED_ORIGINS", raising=False)
    config = ClientConfig(exam_origin="https://exam.example", backend_url="https://api.example")
    assert config.allowed_origins == ("https://exam.example", "https://api.example")
    assert config.build_exam_url("A&B") == "https://exam.example/exam/room?room=A%26B&embedded=1"
