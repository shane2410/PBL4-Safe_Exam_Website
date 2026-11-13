"""Test cho bản vá #3 (thu hồi thiết bị) và A6 (cấu hình production).

#3 — Trước đây `ClientDeviceService.register` tự xoá `revoked_at` khi client
đăng ký lại, nên "thu hồi thiết bị" vô tác dụng: client luôn register trước khi
attest, và mỗi lần chạy lại là tự mở khoá.

A6 — `SECRET_KEY` và `DATABASE_URL` từng có default trong source. Chạy
production mà quên cấu hình nghĩa là bất kỳ ai đọc source cũng ký được JWT.

Chạy: cd backend && .venv/bin/python -m pytest tests/test_device_revocation_and_config.py -v
"""

import base64
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.config import DEV_DATABASE_URL, DEV_SECRET_KEY, Settings
from app.models.client_device import ClientDevice
from app.schemas.client_device_schema import ClientDeviceRegisterRequest
from app.services.client_device_service import ClientDeviceService, DeviceKeyError


def _public_key_b64(seed: int = 1) -> str:
    """Public key 32 byte giả lập (chỉ cần đúng độ dài để qua validator)."""
    return base64.b64encode(bytes([seed] * 32)).decode()


def _register(db, user, seed=1):
    return ClientDeviceService.register(
        db, user, ClientDeviceRegisterRequest(public_key=_public_key_b64(seed))
    )


# --- #3: thu hồi thiết bị ---

def test_register_new_device(db, seeded):
    res = _register(db, seeded["student"])
    assert res.already_registered is False
    assert db.query(ClientDevice).count() == 1


def test_revoked_device_cannot_re_register(db, seeded):
    student = seeded["student"]
    _register(db, student)

    device = db.query(ClientDevice).first()
    device.revoked_at = datetime.now(timezone.utc)
    db.commit()

    with pytest.raises(DeviceKeyError) as exc:
        _register(db, student)
    assert str(exc.value) == "DEVICE_REVOKED"

    db.refresh(device)
    assert device.revoked_at is not None, "Đăng ký lại KHÔNG được tự mở khoá"


def test_admin_unrevoke_restores_registration(db, seeded):
    student = seeded["student"]
    _register(db, student)

    device = db.query(ClientDevice).first()
    device.revoked_at = datetime.now(timezone.utc)
    db.commit()

    # ADMIN mở khoá thủ công (mô phỏng endpoint /admin/devices/{id}/revoke revoke=false)
    device.revoked_at = None
    db.commit()

    res = _register(db, student)
    assert res.already_registered is True


def test_revoked_device_cannot_attest(db, seeded):
    from app.services.client_device_service import ED25519_PUBLIC_KEY_BYTES  # noqa: F401

    student = seeded["student"]
    _register(db, student)
    device = db.query(ClientDevice).first()
    device.revoked_at = datetime.now(timezone.utc)
    db.commit()

    with pytest.raises(DeviceKeyError) as exc:
        ClientDeviceService.get_active(db, student.id, device.device_id)
    assert str(exc.value) == "DEVICE_REVOKED"


def test_revoke_is_per_device_not_per_user(db, seeded):
    """Thu hồi 1 thiết bị không được chặn thiết bị khác của cùng thí sinh."""
    student = seeded["student"]
    _register(db, student, seed=1)
    _register(db, student, seed=2)

    first = db.query(ClientDevice).order_by(ClientDevice.id).first()
    first.revoked_at = datetime.now(timezone.utc)
    db.commit()

    second = db.query(ClientDevice).order_by(ClientDevice.id.desc()).first()
    assert ClientDeviceService.get_active(db, student.id, second.device_id) is not None

    res = _register(db, student, seed=2)
    assert res.already_registered is True


# --- A6: cấu hình production ---

def test_development_allows_defaults():
    s = Settings(_env_file=None, ENV="development")
    assert s.is_production is False
    assert s.SECRET_KEY == DEV_SECRET_KEY


def test_production_rejects_default_secret():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, ENV="production")
    msg = str(exc.value)
    assert "SECRET_KEY" in msg
    assert "DATABASE_URL" in msg


def test_production_rejects_short_secret():
    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            ENV="production",
            SECRET_KEY="short",
            DATABASE_URL="mysql+pymysql://u:p@db:3306/x",
        )
    assert "quá ngắn" in str(exc.value)


def test_production_accepts_strong_config():
    s = Settings(
        _env_file=None,
        ENV="production",
        SECRET_KEY="x" * 64,
        DATABASE_URL="mysql+pymysql://examuser:strongpw@db:3306/exam?charset=utf8mb4",
    )
    assert s.is_production is True


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            ENV="production",
            SECRET_KEY="x" * 64,
            DATABASE_URL="mysql+pymysql://u:p@db:3306/x",
            CORS_ORIGINS=["*"],
        )
    assert "CORS_ORIGINS" in str(exc.value)
