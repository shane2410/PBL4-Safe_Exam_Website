"""Công cụ tạo file cấu hình `.seb` mẫu để phát cho thí sinh.

Vì sao có công cụ này: giảng viên phải phát hành **một file** cho mỗi kỳ thi.
Viết tay plist XML là chỗ dễ sai nhất (thiếu `startURL` thì client không mở
được gì, đặt sai `clipboardPolicy` thì thí sinh copy được đề).

Dùng:
    python -m sebclient.make_seb \\
        --url "http://localhost:5173/exam/room?room=PBL4-EXAM-01" \\
        --out exam-pbl4.seb

    # Khoá chặt hơn, cho phép thêm origin của backend
    python -m sebclient.make_seb \\
        --url "http://localhost:5173/exam/room?room=PBL4-EXAM-01" \\
        --allow-origin http://127.0.0.1:8000 \\
        --no-print --no-copy --lock-quit \\
        --out exam-pbl4.seb
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config_file import BrowserPolicy, build_config_bytes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sebclient.make_seb",
        description="Tạo file cấu hình .seb cho SEB Client",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL trang thi (startURL). Phải là http:// hoặc https://",
    )
    parser.add_argument("--out", default="exam.seb", help="Đường dẫn file xuất (mặc định: exam.seb)")
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="Origin bổ sung được phép nạp (lặp lại được). VD: http://127.0.0.1:8000",
    )

    permissions = parser.add_argument_group("quyền được cấp")
    permissions.add_argument("--allow-print", action="store_true", default=False, help="Cho phép in")
    permissions.add_argument(
        "--allow-copy", action="store_true", default=False, help="Cho phép copy/paste"
    )
    permissions.add_argument(
        "--allow-right-mouse", action="store_true", default=False, help="Cho phép menu chuột phải"
    )
    permissions.add_argument(
        "--allow-devtools", action="store_true", default=False, help="Cho phép DevTools"
    )
    permissions.add_argument(
        "--allow-alt-tab", action="store_true", default=False, help="Không chặn Alt+Tab"
    )
    permissions.add_argument(
        "--allow-address-bar", action="store_true", default=False, help="Hiện thanh địa chỉ"
    )
    permissions.add_argument(
        "--allow-reload", action="store_true", default=True, help="Cho phép tải lại trang"
    )

    quit_group = parser.add_argument_group("thoát chương trình")
    quit_group.add_argument(
        "--lock-quit",
        action="store_true",
        default=False,
        help="Không cho thí sinh tự thoát (cần mật khẩu giám thị)",
    )
    quit_group.add_argument(
        "--quit-password-hash",
        default="",
        help="Hash SHA-256 của mật khẩu giám thị (dùng cùng --lock-quit)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    start_url = args.url.strip()
    if not start_url.startswith(("http://", "https://")):
        print("Lỗi: --url phải bắt đầu bằng http:// hoặc https://", file=sys.stderr)
        return 2

    if args.lock_quit and not args.quit_password_hash:
        print(
            "Cảnh báo: --lock-quit không kèm --quit-password-hash.\n"
            "         Thí sinh sẽ không thoát được kể cả khi máy gặp sự cố.\n"
            "         Client vẫn cho đóng cửa sổ để tránh kẹt cứng.",
            file=sys.stderr,
        )

    policy = BrowserPolicy(
        start_url=start_url,
        allow_print=args.allow_print,
        allow_copy_paste=args.allow_copy,
        allow_right_mouse=args.allow_right_mouse,
        allow_devtools=args.allow_devtools,
        allow_address_bar=args.allow_address_bar,
        allow_reload=args.allow_reload,
        block_alt_tab=not args.allow_alt_tab,
        allow_quit=not args.lock_quit,
        hashed_quit_password=args.quit_password_hash,
    )

    out_path = Path(args.out).expanduser().resolve()
    if out_path.suffix.lower() not in {".seb", ".seb2"}:
        out_path = out_path.with_suffix(".seb")

    data = build_config_bytes(policy)

    # Thêm origin phụ bằng cách chèn key `whitelistURLFilter` — client đọc khoá
    # này, và SEB thật cũng hiểu.
    if args.allow_origin:
        import plistlib

        parsed = plistlib.loads(data)
        parsed["whitelistURLFilter"] = "\n".join(
            [start_url] + args.allow_origin
        )
        data = plistlib.dumps(parsed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)

    print(f"Đã tạo: {out_path} ({len(data)} byte)")
    print(f"  startURL : {start_url}")
    print(f"  cho phép : print={args.allow_print} copy={args.allow_copy} "
          f"right_mouse={args.allow_right_mouse} devtools={args.allow_devtools} "
          f"alt_tab={args.allow_alt_tab}")
    print(f"  thoát    : {'bị khoá' if args.lock_quit else 'tự do'}")
    if args.allow_origin:
        print(f"  origin+  : {', '.join(args.allow_origin)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
