"""Kiểm tra toàn vẹn ứng dụng SEB Client (Self-check SHA-256).

Ngăn chặn việc sửa đổi binary/bytecode và chạy bản bị patch.
- Trong chế độ phát hành (frozen/packaged), tính hash SHA-256 của file binary hoặc
  tập hợp các module cốt lõi, so sánh với BASE_HASH được nhúng sẵn trong constants.py.
- Nếu BASE_HASH = None: coi là môi trường phát triển (dev mode), bỏ qua việc dừng ứng dụng.
- Nếu hash không khớp: ghi log CRITICAL và dừng chương trình (raise SystemExit).
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import sys

from ..constants import BASE_HASH

logger = logging.getLogger(__name__)

# Danh sách tên các module cốt lõi cần kiểm tra toàn vẹn khi chạy từ mã nguồn.
CRITICAL_RELATIVE_MODULES = [
    "__main__.py",
    "app.py",
    "constants.py",
    "integrity/self_check.py",
    "integrity/anti_debug.py",
    "integrity/license_check.py",
    "api/client.py",
    "api/attestation.py",
    "guards/keyboard_guard.py",
    "guards/kiosk_guard.py",
    "ui/exam_window.py",
]


def compute_file_hash(file_path: Path | str) -> str:
    """Tính mã băm SHA-256 của một file cụ thể."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file để tính hash: {path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_critical_files(base_dir: Path | str | None = None) -> list[Path]:
    """Lấy danh sách các file module cốt lõi cần kiểm tra."""
    if base_dir is None:
        # Thư mục gốc sebclient/
        base_dir = Path(__file__).resolve().parent.parent
    else:
        base_dir = Path(base_dir).resolve()

    files: list[Path] = []
    for rel in CRITICAL_RELATIVE_MODULES:
        p = base_dir / rel
        if p.is_file():
            files.append(p)
    return sorted(files)


def compute_hash(
    target_files: list[Path | str] | None = None,
    base_dir: Path | str | None = None,
) -> str:
    """Tính SHA-256 tổng thể của SEB Client.

    - Nếu ứng dụng đã được đóng gói (frozen binary), tính hash của sys.executable.
    - Nếu chạy từ mã nguồn hoặc truyền danh sách file cụ thể: tính hash SHA-256 kết hợp
      của __main__.py và các module quan trọng. Hàm này có thể được gọi bởi build script
      để tạo ra giá trị nhúng vào constants.BASE_HASH hoặc đăng ký lên backend.
    """
    if getattr(sys, "frozen", False) and target_files is None:
        return compute_file_hash(sys.executable)

    files_to_hash: list[Path]
    if target_files is not None:
        files_to_hash = sorted([Path(f).resolve() for f in target_files])
    else:
        files_to_hash = get_critical_files(base_dir)

    if not files_to_hash:
        logger.warning("Không tìm thấy file cốt lõi nào để tính hash")
        return hashlib.sha256(b"").hexdigest()

    master_hasher = hashlib.sha256()
    for file_path in files_to_hash:
        rel_name = file_path.name
        master_hasher.update(rel_name.encode("utf-8"))
        # Tính hash từng file và đưa vào master hasher
        file_sha256 = compute_file_hash(file_path)
        master_hasher.update(file_sha256.encode("utf-8"))

    return master_hasher.hexdigest()


def verify_self_integrity(expected_hash: str | None = None) -> str:
    """Kiểm tra tính toàn vẹn của file thực thi.

    Nếu expected_hash là None, fallback về constants.BASE_HASH.
    Nếu vẫn là None -> chế độ dev, chỉ log và trả về hash hiện tại.
    Nếu hash không khớp -> log CRITICAL và raise SystemExit.
    """
    if expected_hash is None:
        expected_hash = BASE_HASH

    current_hash = compute_hash()

    if expected_hash is None:
        logger.debug(
            "BASE_HASH chưa được thiết lập (chế độ phát triển). Hash hiện tại: %s",
            current_hash,
        )
        return current_hash

    if current_hash.lower() != expected_hash.strip().lower():
        msg = (
            f"Phát hiện can thiệp nhị phân hoặc sửa đổi mã nguồn! "
            f"Kỳ vọng: {expected_hash}, Thực tế: {current_hash}"
        )
        logger.critical(msg)
        raise SystemExit(f"CRITICAL: {msg}")

    logger.info("Xác thực toàn vẹn mã nguồn thành công (SHA-256: %s)", current_hash[:16])
    return current_hash
