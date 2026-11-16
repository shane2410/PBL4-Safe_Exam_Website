#!/usr/bin/env bash
# ==============================================================================
# SCRIPT QUẢN TRỊ VÀ TRIỂN KHAI TOÀN DIỆN (DEPLOYMENT AUTOMATION SCRIPT)
# Hệ thống Thi trắc nghiệm trực tuyến An toàn (Secure Online Exam System)
# ==============================================================================

set -eo pipefail

# Màu sắc hiển thị
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Định vị thư mục deploy
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ------------------------------------------------------------------------------
# 1. Kiểm tra Docker và Docker Compose
# ------------------------------------------------------------------------------
check_prerequisites() {
    log_info "Kiểm tra môi trường Docker..."

    if ! command -v docker >/dev/null 2>&1; then
        log_error "Không tìm thấy Docker! Vui lòng cài đặt Docker: https://docs.docker.com/engine/install/"
        exit 1
    fi

    # Kiểm tra Docker daemon đang chạy
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon chưa khởi chạy hoặc user hiện tại không có quyền truy cập docker socket!"
        log_warn "Hãy chạy: sudo systemctl start docker hoặc thêm user vào group docker: sudo usermod -aG docker \$USER"
        exit 1
    fi

    # Xác định cú pháp docker compose
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        log_error "Không tìm thấy Docker Compose (v2 plugin hoặc docker-compose v1)!"
        exit 1
    fi

    log_success "Docker và Docker Compose ($($COMPOSE_CMD version --short 2>/dev/null || echo 'v2')) đã sẵn sàng."
}

# ------------------------------------------------------------------------------
# 2. Khởi tạo file .env từ template nếu chưa có
# ------------------------------------------------------------------------------
setup_environment() {
    if [ ! -f "${ENV_FILE}" ]; then
        log_warn "Không tìm thấy file cấu hình '${ENV_FILE}'."
        if [ -f "${ENV_EXAMPLE}" ]; then
            log_info "Đang tự động khởi tạo '${ENV_FILE}' từ '${ENV_EXAMPLE}'..."
            cp "${ENV_EXAMPLE}" "${ENV_FILE}"

            # Tự động sinh SECRET_KEY ngẫu nhiên 64 ký tự an toàn
            RANDOM_SECRET=""
            if command -v openssl >/dev/null 2>&1; then
                RANDOM_SECRET=$(openssl rand -hex 32)
            elif command -v python3 >/dev/null 2>&1; then
                RANDOM_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
            else
                RANDOM_SECRET=$(head -c 32 /dev/urandom | xxd -p -c 32 2>/dev/null || date +%s%N | sha256sum | head -c 64)
            fi

            # Tự động sinh mật khẩu database ngẫu nhiên
            RANDOM_DB_PASS=""
            if command -v openssl >/dev/null 2>&1; then
                RANDOM_DB_PASS=$(openssl rand -base64 18 | tr -dc 'a-zA-Z0-9' | head -c 16)
            else
                RANDOM_DB_PASS="Pass_$(date +%s%N | head -c 12)"
            fi

            # Thay thế vào file .env
            if [ -n "${RANDOM_SECRET}" ]; then
                sed -i "s|SECRET_KEY=.*|SECRET_KEY=${RANDOM_SECRET}|" "${ENV_FILE}"
            fi
            if [ -n "${RANDOM_DB_PASS}" ]; then
                sed -i "s|MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=${RANDOM_DB_PASS}|" "${ENV_FILE}"
            fi

            chmod 600 "${ENV_FILE}"
            log_success "Đã tạo '${ENV_FILE}' với SECRET_KEY và MYSQL_ROOT_PASSWORD ngẫu nhiên an toàn."
            log_warn "Hãy mở '${ENV_FILE}' kiểm tra lại CORS_ORIGINS để khớp với domain máy chủ nếu cần!"
        else
            log_error "Không tìm thấy '${ENV_EXAMPLE}' để sao chép template!"
            exit 1
        fi
    else
        log_info "Sử dụng file cấu hình hiện tại: '${ENV_FILE}'"
    fi
}

# ------------------------------------------------------------------------------
# 3. Lệnh triển khai (Build & Up)
# ------------------------------------------------------------------------------
cmd_up() {
    check_prerequisites
    setup_environment

    log_info "Bắt đầu build và khởi động các container..."
    cd "${SCRIPT_DIR}"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build

    log_info "Đang chờ dịch vụ ổn định..."
    sleep 3

    log_success "Các container đã được kích hoạt thành công!"
    cmd_status

    echo ""
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${GREEN}🎉 HỆ THỐNG ĐÃ SẴN SÀNG HOẠT ĐỘNG!${NC}"
    echo -e "${CYAN}================================================================${NC}"
    echo -e "🌐 Giao diện Web:      http://localhost (hoặc IP / domain của máy chủ)"
    echo -e "🔌 Backend API:        http://localhost/api/docs"
    echo -e "⚡ WebSocket:          http://localhost/socket.io/"
    echo -e "👤 Tài khoản mẫu:      admin / admin123  (Quản trị viên)"
    echo -e "                       teacher1 / teacher123  (Giảng viên)"
    echo -e "                       student1 / student123  (Sinh viên)"
    echo -e "📝 Phòng thi mẫu:      Mã phòng: PBL4-EXAM-01"
    echo -e "${CYAN}================================================================${NC}"
    echo -e "Gợi ý lệnh tiếp theo:"
    echo -e "  - Xem log:         $0 logs"
    echo -e "  - Kiểm tra trạng thái: $0 status"
    echo -e "  - Dừng hệ thống:   $0 down"
    echo -e "${CYAN}================================================================${NC}"
}

# ------------------------------------------------------------------------------
# 4. Lệnh dừng hệ thống (Down)
# ------------------------------------------------------------------------------
cmd_down() {
    check_prerequisites
    log_info "Đang dừng và hạ các container..."
    cd "${SCRIPT_DIR}"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" down
    log_success "Đã dừng các container an toàn (dữ liệu CSDL vẫn được bảo lưu trong volume mysql_data)."
}

# ------------------------------------------------------------------------------
# 5. Lệnh khởi động lại (Restart)
# ------------------------------------------------------------------------------
cmd_restart() {
    check_prerequisites
    log_info "Khởi động lại toàn bộ dịch vụ..."
    cd "${SCRIPT_DIR}"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" restart
    log_success "Đã khởi động lại toàn bộ dịch vụ."
    cmd_status
}

# ------------------------------------------------------------------------------
# 6. Xem trạng thái các container (Status)
# ------------------------------------------------------------------------------
cmd_status() {
    check_prerequisites
    echo ""
    log_info "Trạng thái các container:"
    cd "${SCRIPT_DIR}"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps
}

# ------------------------------------------------------------------------------
# 7. Xem log thời gian thực (Logs)
# ------------------------------------------------------------------------------
cmd_logs() {
    check_prerequisites
    SERVICE="${1:-}"
    cd "${SCRIPT_DIR}"
    if [ -n "$SERVICE" ]; then
        log_info "Theo dõi logs của service '$SERVICE' (Nhấn Ctrl+C để thoát)..."
        $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs -f "$SERVICE"
    else
        log_info "Theo dõi logs toàn bộ hệ thống (Nhấn Ctrl+C để thoát)..."
        $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" logs -f --tail=100
    fi
}

# ------------------------------------------------------------------------------
# 8. Nạp lại dữ liệu mẫu (Seed)
# ------------------------------------------------------------------------------
cmd_seed() {
    check_prerequisites
    log_info "Đang thực thi seeder tạo dữ liệu mẫu trong container backend..."
    cd "${SCRIPT_DIR}"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec backend python -m seeders.seed_data
    log_success "Nạp dữ liệu mẫu hoàn tất!"
}

# ------------------------------------------------------------------------------
# 9. Chạy Migration CSDL (Migrate)
# ------------------------------------------------------------------------------
cmd_migrate() {
    check_prerequisites
    log_info "Đang chạy Alembic migration trong container backend..."
    cd "${SCRIPT_DIR}"
    $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec backend alembic upgrade head
    log_success "Áp dụng migration hoàn tất!"
}

# ------------------------------------------------------------------------------
# 10. Sao lưu Cơ sở dữ liệu (Backup)
# ------------------------------------------------------------------------------
cmd_backup() {
    check_prerequisites
    BACKUP_DIR="${SCRIPT_DIR}/backups"
    mkdir -p "${BACKUP_DIR}"
    TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
    BACKUP_FILE="${BACKUP_DIR}/exam_db_${TIMESTAMP}.sql.gz"

    log_info "Đang sao lưu CSDL vào '${BACKUP_FILE}'..."
    cd "${SCRIPT_DIR}"
    # Đọc cấu hình mật khẩu từ .env
    set -a
    [ -f "${ENV_FILE}" ] && . "${ENV_FILE}"
    set +a

    $COMPOSE_CMD -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T db \
        mysqldump -u root -p"${MYSQL_ROOT_PASSWORD:-exam_secure_root_password_2026}" \
        --default-character-set=utf8mb4 --single-transaction --quick \
        "${MYSQL_DATABASE:-secure_exam_db}" | gzip > "${BACKUP_FILE}"

    log_success "Sao lưu thành công! Kích thước file: $(du -h "${BACKUP_FILE}" | cut -f1)"
}

# ------------------------------------------------------------------------------
# Hướng dẫn sử dụng
# ------------------------------------------------------------------------------
cmd_help() {
    echo -e "${CYAN}================================================================${NC}"
    echo -e "  HỆ THỐNG THI TRẮC NGHIỆM TRỰC TUYẾN - SCRIPT QUẢN TRỊ DEPLOY"
    echo -e "${CYAN}================================================================${NC}"
    echo "Cách dùng: $0 [LỆNH]"
    echo ""
    echo "Các lệnh khả dụng:"
    echo "  up              Build và khởi động toàn bộ hệ thống ở chế độ nền (Mặc định)"
    echo "  down            Dừng và hạ tất cả các container"
    echo "  restart         Khởi động lại toàn bộ dịch vụ"
    echo "  status | ps     Xem trạng thái các container"
    echo "  logs [service]  Xem log trực tiếp (vd: $0 logs backend hoặc $0 logs web)"
    echo "  seed            Chạy lại seeder nạp dữ liệu mẫu ban đầu"
    echo "  migrate         Chạy migration database (alembic upgrade head)"
    echo "  backup          Tạo file sao lưu CSDL MySQL nén (.sql.gz) vào thư mục backups/"
    echo "  help            Hiển thị trợ giúp này"
    echo ""
}

# ------------------------------------------------------------------------------
# Điều hướng tham số dòng lệnh
# ------------------------------------------------------------------------------
ACTION="${1:-up}"
shift || true

case "${ACTION}" in
    up)
        cmd_up
        ;;
    down)
        cmd_down
        ;;
    restart)
        cmd_restart
        ;;
    status|ps)
        cmd_status
        ;;
    logs)
        cmd_logs "$@"
        ;;
    seed)
        cmd_seed
        ;;
    migrate)
        cmd_migrate
        ;;
    backup)
        cmd_backup
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        log_error "Lệnh '${ACTION}' không hợp lệ!"
        cmd_help
        exit 1
        ;;
esac
