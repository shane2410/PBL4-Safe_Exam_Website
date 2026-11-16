"""Kiểm tra giấy phép và phiên bản tối thiểu của SEB Client (Phase 2).

So sánh phiên bản hiện tại (CLIENT_VERSION trong constants.py) với cấu hình
`min_version` từ server (thuộc seb_client_config của settings_service) bằng
`packaging.version`.
Nếu client cũ hơn yêu cầu tối thiểu:
- Ghi log CRITICAL.
- Hiển thị hộp thoại (dialog) thông báo cho thí sinh yêu cầu cập nhật.
- Buộc dừng tiến trình (raise SystemExit).
"""

from __future__ import annotations

import logging
import re
import sys

from packaging.version import InvalidVersion, Version, parse

from ..constants import CLIENT_VERSION

logger = logging.getLogger(__name__)


def parse_version_safe(ver_str: str) -> Version:
    """Chuyển chuỗi phiên bản thành đối tượng packaging.version.Version.

    Tự động chuẩn hoá các hậu tố SemVer (như -phase1, +build123) để không bị
    lỗi InvalidVersion theo chuẩn PEP 440.
    """
    clean_str = ver_str.strip()
    try:
        return parse(clean_str)
    except InvalidVersion:
        # Tách phần tiền tố semver chính (x.y.z)
        base = re.split(r"[-+]", clean_str)[0].strip()
        try:
            return parse(base)
        except InvalidVersion:
            logger.error("Không thể phân tích phiên bản: %r, fallback về 0.0.0", ver_str)
            return parse("0.0.0")


def is_version_supported(
    min_version: str,
    current_version: str = CLIENT_VERSION,
) -> bool:
    """So sánh phiên bản client hiện tại với min_version.

    Trả về True nếu current_version >= min_version.
    """
    if not min_version or not min_version.strip():
        return True

    curr_v = parse_version_safe(current_version)
    min_v = parse_version_safe(min_version)

    return curr_v >= min_v


def show_update_dialog(min_version: str, current_version: str = CLIENT_VERSION) -> None:
    """Hiển thị hộp thoại cảnh báo bắt buộc nâng cấp client cho người dùng."""
    msg = (
        f"Phiên bản SEB Client hiện tại ({current_version}) đã lỗi thời và không còn được chấp nhận.\n"
        f"Phiên bản tối thiểu yêu cầu bởi hệ thống: {min_version}.\n\n"
        f"Vui lòng tải và cài đặt phiên bản SEB Client mới nhất từ cổng thông tin thi để tiếp tục."
    )
    logger.critical("Yêu cầu cập nhật: %s", msg)

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        created_app = False
        if app is None:
            app = QApplication(sys.argv)
            created_app = True

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Yêu cầu cập nhật SEB Client")
        msg_box.setText(msg)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không thể hiển thị dialog cập nhật client: %s", exc)


def enforce_min_version(
    min_version: str | None,
    current_version: str = CLIENT_VERSION,
    show_dialog: bool = True,
) -> None:
    """Kiểm tra và thực thi phiên bản tối thiểu. Thoát nếu không đáp ứng."""
    if not min_version:
        return

    if not is_version_supported(min_version, current_version):
        detail = (
            f"Phiên bản SEB Client ({current_version}) không đáp ứng yêu cầu tối thiểu ({min_version})."
        )
        logger.critical(detail)
        if show_dialog:
            show_update_dialog(min_version, current_version)
        raise SystemExit(f"CRITICAL: {detail}")

    logger.info(
        "Kiểm tra phiên bản hợp lệ: %s >= %s",
        current_version,
        min_version,
    )
