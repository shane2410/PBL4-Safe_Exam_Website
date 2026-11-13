#!/usr/bin/env bash
# Đóng gói SEB Client bằng PyInstaller.
#
# Dùng:
#   ./packaging/build.sh            # build cho hệ điều hành hiện tại
#   ./packaging/build.sh linux      # ép build Linux
#   ./packaging/build.sh windows    # build .exe qua Wine + Python 3.11 trong prefix
#
# Kết quả: seb_client/dist/SEB-Client/ (Linux) hoặc
#          seb_client/dist-win/SEB-Client/ (Windows)
#
# Vì sao phải build Windows trên Windows/Wine: PyInstaller KHÔNG cross-compile.
# Nó đóng gói chính thư viện của nền tảng đang chạy (QtWebEngine .dll vs .so),
# nên build trên Linux chỉ ra sản phẩm Linux.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
TARGET="${1:-auto}"

if [[ "$TARGET" == "auto" ]]; then
  case "$(uname -s)" in
    Linux)  [[ -n "${SEB_BUILD_WINDOWS:-}" ]] && TARGET=windows || TARGET=linux ;;
    Darwin) TARGET=macos ;;
    *)      TARGET=windows ;;
  esac
fi

PYINSTALLER_ARGS=(--noconfirm --clean)

case "$TARGET" in
  linux|macos)
    PY="$ROOT/.venv/bin/python"
    if [[ ! -x "$PY" ]]; then
      echo "Không thấy $PY — tạo venv trước: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
      exit 1
    fi
    if ! "$PY" -c "import PyInstaller" >/dev/null 2>&1; then
      echo "Chưa có PyInstaller. Chạy: $PY -m pip install 'pyinstaller==6.21.0'"
      exit 1
    fi
    rm -rf "$ROOT/dist" "$ROOT/build"
    "$PY" -m PyInstaller "${PYINSTALLER_ARGS[@]}" \
      --distpath "$ROOT/dist" --workpath "$ROOT/build" \
      "$HERE/seb_client.spec"
    cp "$ROOT/.env.example" "$ROOT/dist/SEB-Client/.env.example"
    echo
    echo "Xong: $ROOT/dist/SEB-Client/SEB-Client"
    echo "Cấu hình: copy .env.example -> .env trong cùng thư mục rồi sửa."
    ;;

  windows)
    # Python cho Windows trong prefix Wine. Đổi qua WIN_PYTHON nếu cài chỗ khác.
    WIN_PYTHON="${WIN_PYTHON:-C:\\Program Files\\Python311\\python.exe}"
    if ! wine "$WIN_PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
      echo "Python trong Wine chưa có PyInstaller. Chạy trước:"
      echo "  wine \"$WIN_PYTHON\" -m pip install -r \"$(winepath -w "$ROOT/requirements.txt")\" \"pyinstaller==6.21.0\""
      exit 1
    fi
    rm -rf "$ROOT/dist-win" "$ROOT/build-win"
    wine "$WIN_PYTHON" -m PyInstaller "${PYINSTALLER_ARGS[@]}" \
      --distpath "$(winepath -w "$ROOT/dist-win")" \
      --workpath "$(winepath -w "$ROOT/build-win")" \
      "$(winepath -w "$HERE/seb_client.spec")"
    cp "$ROOT/.env.example" "$ROOT/dist-win/SEB-Client/.env.example"
    echo
    echo "Xong: $ROOT/dist-win/SEB-Client/SEB-Client.exe"
    echo "Cấu hình: copy .env.example -> .env trong cùng thư mục rồi sửa."
    ;;

  *)
    echo "Nền tảng không hỗ trợ: $TARGET (chỉ linux | macos | windows)"
    exit 2
    ;;
esac
