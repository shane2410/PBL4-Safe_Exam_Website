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
      echo "Không thấy $PY — tự động khởi tạo .venv tại $ROOT/.venv..."
      python3 -m venv "$ROOT/.venv"
      PY="$ROOT/.venv/bin/python"
    fi

    echo "==> (a) Cài đặt dependencies từ requirements.txt và pyinstaller..."
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install -r "$ROOT/requirements.txt" "pyinstaller==6.21.0"

    echo "==> (b) Chạy PyInstaller với seb_client.spec..."
    rm -rf "$ROOT/dist" "$ROOT/build"
    "$PY" -m PyInstaller "${PYINSTALLER_ARGS[@]}" \
      --distpath "$ROOT/dist" --workpath "$ROOT/build" \
      "$HERE/seb_client.spec"
    cp "$ROOT/.env.example" "$ROOT/dist/SEB-Client/.env.example"

    BINARY="$ROOT/dist/SEB-Client/SEB-Client"
    SHA_FILE="$ROOT/dist/seb_client.sha256"

    echo
    echo "==> (c) & (d) Tính và lưu SHA-256 của binary output..."
    if [[ -f "$BINARY" ]]; then
      "$PY" -c "
import hashlib, sys
from pathlib import Path

bin_path = Path(sys.argv[1])
sha_path = Path(sys.argv[2])

h = hashlib.sha256(bin_path.read_bytes()).hexdigest()
line = f'{h}  {bin_path.name}\n'
sys.stdout.write(f'SHA-256 ({bin_path.name}): {h}\n')
sha_path.write_text(line, encoding='utf-8')
" "$BINARY" "$SHA_FILE"
      echo "Đã ghi checksum vào: $SHA_FILE"
    else
      echo "CẢNH BÁO: Không tìm thấy binary tại $BINARY"
    fi

    echo
    echo "Xong: $ROOT/dist/SEB-Client/SEB-Client"
    echo "Cấu hình: copy .env.example -> .env trong cùng thư mục rồi sửa."
    ;;

  windows)
    # Python cho Windows trong prefix Wine. Đổi qua WIN_PYTHON nếu cài chỗ khác.
    WIN_PYTHON="${WIN_PYTHON:-C:\\Program Files\\Python311\\python.exe}"
    echo "==> (a) Cài đặt dependencies và PyInstaller trong Wine..."
    wine "$WIN_PYTHON" -m pip install -r "$(winepath -w "$ROOT/requirements.txt")" "pyinstaller==6.21.0"

    echo "==> (b) Chạy PyInstaller với seb_client.spec..."
    rm -rf "$ROOT/dist-win" "$ROOT/build-win"
    wine "$WIN_PYTHON" -m PyInstaller "${PYINSTALLER_ARGS[@]}" \
      --distpath "$(winepath -w "$ROOT/dist-win")" \
      --workpath "$(winepath -w "$ROOT/build-win")" \
      "$(winepath -w "$HERE/seb_client.spec")"
    cp "$ROOT/.env.example" "$ROOT/dist-win/SEB-Client/.env.example"

    WIN_BINARY="$ROOT/dist-win/SEB-Client/SEB-Client.exe"
    WIN_SHA_FILE="$ROOT/dist-win/seb_client.sha256"

    echo
    echo "==> (c) & (d) Tính và lưu SHA-256 của binary output..."
    if [[ -f "$WIN_BINARY" ]]; then
      if command -v sha256sum >/dev/null 2>&1; then
        (cd "$ROOT/dist-win/SEB-Client" && sha256sum "SEB-Client.exe") | tee "$WIN_SHA_FILE"
      fi
      echo "Đã ghi checksum Windows vào: $WIN_SHA_FILE"
    fi

    echo
    echo "Xong: $ROOT/dist-win/SEB-Client/SEB-Client.exe"
    echo "Cấu hình: copy .env.example -> .env trong cùng thư mục rồi sửa."
    ;;

  *)
    echo "Nền tảng không hỗ trợ: $TARGET (chỉ linux | macos | windows)"
    exit 2
    ;;
esac
