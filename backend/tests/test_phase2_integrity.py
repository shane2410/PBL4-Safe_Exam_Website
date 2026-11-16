"""Tests cho Phase 2: Chống crack & xác thực tính toàn vẹn SEB Client."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from app.api.routers.admin_router import create_client_release, list_client_releases
from app.api.routers.auth_router import get_client_config
from app.dependencies.client_identity import ClientIdentity
from app.models.signed_client_release import SignedClientRelease
from app.models.violation_log import ViolationLog
from app.schemas.client_release_schema import ClientReleaseCreate
from app.services.exam_security_service import ExamSecurityService
from app.services.exam_session_service import ExamSessionService
from app.services.settings_service import SettingsService


VALID_HASH_1 = "a" * 64
VALID_HASH_2 = "b" * 64
INVALID_HASH = "c" * 64


# ============================================================================
# 1. Admin Signed Client Releases API & Model Tests
# ============================================================================

def test_create_and_list_client_release(db, seeded):
    admin = seeded["admin"]
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    payload = ClientReleaseCreate(
        version="1.0.0",
        hash=VALID_HASH_1,
        os="windows",
        is_active=True,
        notes="Bản phát hành chính thức 1.0.0",
    )

    created = create_client_release(
        payload=payload,
        request=mock_request,
        db=db,
        current_user=admin,
    )
    assert created.id is not None
    assert created.version == "1.0.0"
    assert created.hash == VALID_HASH_1
    assert created.os == "windows"
    assert created.is_active is True

    # Test listing releases
    all_releases = list_client_releases(db=db, current_user=admin)
    assert len(all_releases) == 1
    assert all_releases[0].hash == VALID_HASH_1

    # Filter by OS
    win_releases = list_client_releases(os_name="windows", db=db, current_user=admin)
    assert len(win_releases) == 1
    mac_releases = list_client_releases(os_name="macos", db=db, current_user=admin)
    assert len(mac_releases) == 0


def test_create_duplicate_release_rejected(db, seeded):
    admin = seeded["admin"]
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"

    payload = ClientReleaseCreate(
        version="1.0.0",
        hash=VALID_HASH_1,
        os="windows",
    )
    create_client_release(payload=payload, request=mock_request, db=db, current_user=admin)

    # Thử tạo lại cùng hash và os
    with pytest.raises(HTTPException) as exc_info:
        create_client_release(payload=payload, request=mock_request, db=db, current_user=admin)
    assert exc_info.value.status_code == 400


def test_client_release_invalid_hash_validation():
    with pytest.raises(ValueError):
        ClientReleaseCreate(version="1.0.0", hash="not_64_chars")

    with pytest.raises(ValueError):
        ClientReleaseCreate(version="1.0.0", hash="z" * 64)  # Không phải hex


# ============================================================================
# 2. Public Client Config API
# ============================================================================

def test_get_client_config(db):
    cfg = get_client_config(db=db)
    assert cfg.min_version is not None
    assert cfg.heartbeat_interval > 0


# ============================================================================
# 3. Hash Validation in join_exam (Phase 2 Integrity Gate)
# ============================================================================

def test_join_exam_when_no_active_releases(db, seeded):
    """Khi bảng signed_client_releases rỗng, cho phép join mà không ép hash."""
    student = seeded["student"]
    schedule = seeded["schedule"]

    identity = ClientIdentity(
        client_type="seb",
        client_version="1.0.0",
        client_hash=VALID_HASH_1,
        device_fingerprint="fp1",
        attested=True,
    )

    res = ExamSessionService.join_exam(
        db=db,
        room_code=schedule.room_code,
        student_id=student.id,
        client_identity=identity,
    )
    assert res.session_token is not None


def test_join_exam_with_valid_hash(db, seeded):
    """Client gửi hash hợp lệ khớp bản phát hành đang active -> thành công."""
    student = seeded["student"]
    schedule = seeded["schedule"]

    # Đăng ký release hợp lệ
    release = SignedClientRelease(
        version="1.0.0",
        hash=VALID_HASH_1,
        os="all",
        is_active=True,
    )
    db.add(release)
    db.commit()

    identity = ClientIdentity(
        client_type="seb",
        client_version="1.0.0",
        client_hash=VALID_HASH_1,
        device_fingerprint="fp1",
        attested=True,
    )

    res = ExamSessionService.join_exam(
        db=db,
        room_code=schedule.room_code,
        student_id=student.id,
        client_identity=identity,
    )
    assert res.session_token is not None


def test_join_exam_invalid_hash_with_safe_browser_required(db, seeded):
    """Khi đề yêu cầu Safe Exam Browser và hash client không hợp lệ:
    - Ghi log CLIENT_HASH_INVALID
    - Đặt attestation_status = FAILED
    - Trả lỗi 403 Forbidden
    """
    student = seeded["student"]
    schedule = seeded["schedule"]
    exam = seeded["exam"]

    # Bật require_safe_browser cả ở đề và hệ thống
    exam.require_safe_browser = True
    SettingsService.set_require_safe_browser_global(db, True, seeded["admin"].id)
    db.commit()

    # Đăng ký release hợp lệ
    release = SignedClientRelease(
        version="1.0.0",
        hash=VALID_HASH_1,
        os="all",
        is_active=True,
    )
    db.add(release)
    db.commit()

    # Client gửi hash giả mạo / bị sửa đổi
    identity = ClientIdentity(
        client_type="seb",
        client_version="1.0.0",
        client_hash=INVALID_HASH,
        device_fingerprint="fp1",
        attested=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        ExamSessionService.join_exam(
            db=db,
            room_code=schedule.room_code,
            student_id=student.id,
            client_identity=identity,
        )

    assert exc_info.value.status_code == 403
    assert "CLIENT_HASH_INVALID" in exc_info.value.detail

    # Kiểm tra vi phạm đã được ghi vào ViolationLog
    violation = db.query(ViolationLog).filter(
        ViolationLog.event_type == "CLIENT_HASH_INVALID"
    ).first()
    assert violation is not None
    assert violation.detail["client_hash"] == INVALID_HASH

    # Kiểm tra phiên thi đã được đặt attestation_status = FAILED
    from app.models.exam_session import ExamSession
    session = db.query(ExamSession).filter(
        ExamSession.student_id == student.id,
        ExamSession.schedule_id == schedule.id,
    ).first()
    assert session is not None
    assert session.attestation_status == "FAILED"
    assert session.client_hash == INVALID_HASH


def test_join_exam_invalid_hash_without_safe_browser_required(db, seeded):
    """Khi đề KHÔNG bắt buộc Safe Exam Browser và client hash không hợp lệ:
    - Ghi log CLIENT_HASH_INVALID
    - Đặt attestation_status = FAILED
    - KHÔNG ném 403 (cho phép tiếp tục làm bài ở chế độ thường)
    """
    student = seeded["student"]
    schedule = seeded["schedule"]
    exam = seeded["exam"]
    exam.require_safe_browser = False
    db.commit()

    # Đăng ký release hợp lệ
    release = SignedClientRelease(
        version="1.0.0",
        hash=VALID_HASH_1,
        os="all",
        is_active=True,
    )
    db.add(release)
    db.commit()

    identity = ClientIdentity(
        client_type="seb",
        client_version="1.0.0",
        client_hash=INVALID_HASH,
        device_fingerprint="fp1",
        attested=True,
    )

    res = ExamSessionService.join_exam(
        db=db,
        room_code=schedule.room_code,
        student_id=student.id,
        client_identity=identity,
    )
    assert res.session_token is not None

    # Kiểm tra log vi phạm CLIENT_HASH_INVALID vẫn được ghi lại
    violation = db.query(ViolationLog).filter(
        ViolationLog.event_type == "CLIENT_HASH_INVALID"
    ).first()
    assert violation is not None
    assert violation.detail["client_hash"] == INVALID_HASH

    from app.models.exam_session import ExamSession
    session = db.query(ExamSession).filter(
        ExamSession.student_id == student.id,
        ExamSession.schedule_id == schedule.id,
    ).first()
    assert session is not None
    assert session.attestation_status == "FAILED"
