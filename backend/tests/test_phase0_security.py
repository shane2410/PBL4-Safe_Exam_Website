"""Test cho Phase 0: toggle 'only through safe exam browser' + cấu hình khoá an toàn.

Chạy: cd backend && .venv/bin/python -m pytest tests/test_phase0_security.py -v
"""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.client_attestation_schema import ClientAttestRequest
from app.schemas.settings_schema import ExamSecurityConfig
from app.schemas.violation_schema import (
    ALLOWED_EVENT_TYPES, ViolationLogCreate, resolve_severity
)
from app.services.attestation_service import (
    AttestationService, build_attest_message
)
from app.services.exam_security_service import ExamSecurityService
from app.services.settings_service import SettingsService


# --- SettingsService ---

def test_default_setting_when_db_empty(db):
    """DB chưa seed -> vẫn trả giá trị mặc định hợp lệ, không ném lỗi."""
    assert SettingsService.get_require_safe_browser_global(db) is False


def test_set_and_get_require_safe_browser(db, seeded):
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()
    assert SettingsService.get_require_safe_browser_global(db) is True


def test_invalid_setting_key_rejected(db):
    with pytest.raises(ValueError):
        SettingsService.get_raw(db, "drop_table_hack")


# --- ExamSecurityService: quyết định require_safe_browser ---

def test_seb_not_required_when_exam_flag_off(db, seeded):
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()
    exam = seeded["exam"]
    assert exam.require_safe_browser is False
    assert ExamSecurityService.is_safe_browser_required(db, exam) is False


def test_seb_required_only_when_both_flags_on(db, seeded):
    exam = seeded["exam"]

    # Chỉ bật cờ đề -> chưa đủ
    exam.require_safe_browser = True
    db.commit()
    assert ExamSecurityService.is_safe_browser_required(db, exam) is False

    # Bật cả cờ hệ thống -> có hiệu lực
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()
    assert ExamSecurityService.is_safe_browser_required(db, exam) is True


def test_exam_can_opt_out_while_global_on(db, seeded):
    """GV tắt yêu cầu cho đề này dù cả hệ thống đang bật."""
    exam = seeded["exam"]
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    exam.require_safe_browser = False
    db.commit()
    assert ExamSecurityService.is_safe_browser_required(db, exam) is False


def test_save_and_resolve_policy(db, seeded):
    exam_id = seeded["exam"].id
    policy = ExamSecurityConfig(max_tab_switch=2, max_fullscreen_exit=1, block_devtools=False)
    ExamSecurityService.save_config(db, exam_id, policy)

    resolved = ExamSecurityService.resolve_policy(db, exam_id)
    assert resolved.max_tab_switch == 2
    assert resolved.max_fullscreen_exit == 1
    assert resolved.block_devtools is False


def test_resolve_policy_falls_back_to_global_default(db, seeded):
    """Đề chưa cấu hình riêng -> dùng mặc định hệ thống."""
    default_cfg = ExamSecurityConfig(max_tab_switch=7)
    SettingsService.set_raw(db, "default_security_config", default_cfg.model_dump())
    db.commit()

    resolved = ExamSecurityService.resolve_policy(db, seeded["exam"].id)
    assert resolved.max_tab_switch == 7


def test_corrupt_policy_falls_back_instead_of_crashing(db, seeded):
    """Cấu hình JSON hỏng trong DB -> fallback, không làm sập luồng vào phòng thi."""
    from app.models.exam_security_config import ExamSecurityConfigRow as ConfigModel
    db.add(ConfigModel(exam_id=seeded["exam"].id, config={"max_tab_switch": "không phải số"}))
    db.commit()

    resolved = ExamSecurityService.resolve_policy(db, seeded["exam"].id)
    assert resolved.max_tab_switch == ExamSecurityConfig().max_tab_switch


# --- Attestation: challenge-response ---

def _make_request(nonce, version, fingerprint, sig):
    """Dựng request hợp lệ cho verify_attestation."""
    return ClientAttestRequest(
        nonce=nonce,
        client_version=version,
        device_fingerprint=fingerprint,
        signature=sig,
    )


def _derive_device_secret(user):
    """Mô phỏng đúng công thức phía server để tạo chữ ký hợp lệ."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"device_secret|{user.id}|{user.device_secret_salt or ''}".encode("utf-8"),
        hashlib.sha256,
    ).digest()


def test_valid_attestation_succeeds(db, seeded):
    user = seeded["student"]
    nonce, ttl = AttestationService.issue_nonce(db, user)
    assert ttl > 0
    assert user.device_secret_salt  # đã được cấp salt

    fingerprint = "fp-abc-123"
    version = "1.0.0"
    message = build_attest_message(nonce, version, fingerprint)
    sig = base64.b64encode(hmac.new(_derive_device_secret(user), message, hashlib.sha256).digest()).decode()

    result = AttestationService.verify_attestation(
        db, user, _make_request(nonce, version, fingerprint, sig)
    )

    assert result.attested is True
    assert result.attestation_key is not None


def test_nonce_is_single_use(db, seeded):
    """Replay cùng một nonce phải thất bại."""
    user = seeded["student"]
    nonce, _ = AttestationService.issue_nonce(db, user)
    fingerprint, version = "fp-1", "1.0.0"
    message = build_attest_message(nonce, version, fingerprint)
    sig = base64.b64encode(hmac.new(_derive_device_secret(user), message, hashlib.sha256).digest()).decode()

    req = _make_request(nonce, version, fingerprint, sig)

    first = AttestationService.verify_attestation(db, user, req)
    second = AttestationService.verify_attestation(db, user, req)

    assert first.attested is True
    assert second.attested is False


def test_wrong_signature_rejected(db, seeded):
    user = seeded["student"]
    nonce, _ = AttestationService.issue_nonce(db, user)
    bogus = base64.b64encode(b"x" * 32).decode()

    result = AttestationService.verify_attestation(
        db, user, _make_request(nonce, "1.0.0", "fp", bogus)
    )

    assert result.attested is False


def test_signature_bound_to_version_and_fingerprint(db, seeded):
    """Đổi version/fingerprint sau khi ký -> chữ ký không còn hợp lệ."""
    user = seeded["student"]
    nonce, _ = AttestationService.issue_nonce(db, user)
    message = build_attest_message(nonce, "1.0.0", "fp-original")
    sig = base64.b64encode(hmac.new(_derive_device_secret(user), message, hashlib.sha256).digest()).decode()

    result = AttestationService.verify_attestation(
        db, user, _make_request(nonce, "1.0.0", "fp-DA_DOI", sig)
    )

    assert result.attested is False


def test_nonce_of_other_user_rejected(db, seeded):
    """Nonce cấp cho user A không dùng được cho user B."""
    user_a, user_b = seeded["student"], seeded["admin"]
    nonce, _ = AttestationService.issue_nonce(db, user_a)
    message = build_attest_message(nonce, "1.0.0", "fp")
    sig = base64.b64encode(hmac.new(_derive_device_secret(user_b), message, hashlib.sha256).digest()).decode()

    result = AttestationService.verify_attestation(
        db, user_b, _make_request(nonce, "1.0.0", "fp", sig)
    )

    assert result.attested is False


def test_nonce_never_stored_in_plaintext_in_db(db, seeded):
    """Khoá bí mật không nằm trong DB — chỉ có salt."""
    user = seeded["student"]
    AttestationService.issue_nonce(db, user)
    row = db.query(type(user)).filter(type(user).id == user.id).first()
    assert row.device_secret_salt is not None
    assert len(row.device_secret_salt) == 32  # hex(16 bytes)


# --- Violation: whitelist + server-side severity ---

def test_event_type_whitelist():
    assert "TAB_SWITCH" in ALLOWED_EVENT_TYPES
    assert "UNAUTHORIZED_CLIENT" in ALLOWED_EVENT_TYPES
    assert "CLIENT_HASH_INVALID" in ALLOWED_EVENT_TYPES
    assert len(ALLOWED_EVENT_TYPES) == 9


def test_unknown_event_type_rejected():
    with pytest.raises(Exception):
        ViolationLogCreate(
            event_type="HACK_INTO_SERVER",
            detail=None,
            client_timestamp=datetime.now(timezone.utc),
        )


def test_severity_resolved_server_side():
    """Client tự khai severity không được dùng — server quyết định từ event_type."""
    assert resolve_severity("DEVTOOLS_DETECTED") == "HIGH"
    assert resolve_severity("TAB_SWITCH") == "LOW"
    assert resolve_severity("UNAUTHORIZED_CLIENT") == "HIGH"
