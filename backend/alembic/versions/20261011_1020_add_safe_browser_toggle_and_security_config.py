"""add_safe_browser_toggle_and_security_config

Phase 0 — bổ sung cơ chế "only through safe exam browser" + cấu hình khoá an toàn.
Xem docs/PLAN.md mục 0.2.

Revision ID: b1f3a9c47d2e
Revises: 7b944b0e6ebd
Create Date: 2026-10-11 10:20:00.000000

"""
from typing import Sequence, Union

import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f3a9c47d2e'
down_revision: Union[str, None] = '7b944b0e6ebd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- exams: cờ bắt buộc dùng Safe Exam Browser Client (cấp đề) ---
    op.add_column(
        'exams',
        sa.Column('require_safe_browser', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )
    op.add_column(
        'exams',
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- exam_sessions: thông tin client cho xác thực & phục tra ---
    op.add_column(
        'exam_sessions',
        sa.Column('client_type', sa.String(length=20), nullable=False, server_default='web'),
    )
    op.add_column('exam_sessions', sa.Column('client_version', sa.String(length=20), nullable=True))
    op.add_column('exam_sessions', sa.Column('device_fingerprint', sa.String(length=128), nullable=True))
    op.add_column(
        'exam_sessions',
        sa.Column('attestation_status', sa.String(length=20), nullable=False, server_default='NOT_ATTESTED'),
    )

    # --- system_settings: cấu hình toàn cục (key-value JSON) ---
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('setting_key', sa.String(length=100), nullable=False),
        sa.Column('setting_value', sa.JSON(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('setting_key'),
    )
    op.create_index(op.f('ix_system_settings_id'), 'system_settings', ['id'], unique=False)
    op.create_index(op.f('ix_system_settings_setting_key'), 'system_settings', ['setting_key'], unique=False)

    # --- exam_security_configs: cấu hình khoá an toàn chi tiết theo đề ---
    op.create_table(
        'exam_security_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('exam_id'),
    )
    op.create_index(op.f('ix_exam_security_configs_id'), 'exam_security_configs', ['id'], unique=False)
    op.create_index(op.f('ix_exam_security_configs_exam_id'), 'exam_security_configs', ['exam_id'], unique=False)

    # --- users: salt dẫn xuất device_secret cho challenge-response ---
    op.add_column('users', sa.Column('device_secret_salt', sa.String(length=64), nullable=True))

    # --- client_attestations: vết challenge-response cho phục tra ---
    op.create_table(
        'client_attestations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('client_type', sa.String(length=20), nullable=False),
        sa.Column('client_version', sa.String(length=20), nullable=True),
        sa.Column('device_fingerprint', sa.String(length=128), nullable=True),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('verification_detail', sa.String(length=255), nullable=True),
        sa.Column('key_salt', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['exam_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_client_attestations_id'), 'client_attestations', ['id'], unique=False)
    op.create_index(op.f('ix_client_attestations_session_id'), 'client_attestations', ['session_id'], unique=False)
    op.create_index('idx_attestation_session', 'client_attestations', ['session_id', 'verified'], unique=False)

    # --- Seed cấu hình mặc định ---
    # Dùng op.execute với SQL literal thay vì bulk_insert: bulk_insert không chạy được
    # biểu thức SQL (CURRENT_TIMESTAMP) trên một số dialect, còn SQL literal thì
    # hoạt động đồng nhất trên cả MySQL lẫn SQLite.
    op.execute(sa.text(
        "INSERT INTO system_settings (setting_key, setting_value, updated_at) "
        "VALUES ('require_safe_browser_global', :v1, CURRENT_TIMESTAMP)"
    ).bindparams(v1=json.dumps(False)))
    op.execute(sa.text(
        "INSERT INTO system_settings (setting_key, setting_value, updated_at) "
        "VALUES ('seb_client_config', :v2, CURRENT_TIMESTAMP)"
    ).bindparams(v2=json.dumps({
        "min_version": "1.0.0",
        "heartbeat_interval": 10,
        "heartbeat_timeout": 30,
        "attestation_required": False,
    })))
    op.execute(sa.text(
        "INSERT INTO system_settings (setting_key, setting_value, updated_at) "
        "VALUES ('default_security_config', :v3, CURRENT_TIMESTAMP)"
    ).bindparams(v3=json.dumps({
        "require_fullscreen": True,
        "block_copy_paste": True,
        "block_devtools": True,
        "detect_devtools": True,
        "monitor_tab_switch": True,
        "lock_navigation": True,
        "disable_print": True,
        "allow_web_fallback": True,
        "max_tab_switch": 5,
        "max_fullscreen_exit": 3,
        "auto_submit_on_threshold": True,
        "warn_countdown_seconds": 10,
    })))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM system_settings WHERE setting_key IN ('require_safe_browser_global', 'seb_client_config', 'default_security_config')"))

    op.drop_index('idx_attestation_session', table_name='client_attestations')
    op.drop_index(op.f('ix_client_attestations_session_id'), table_name='client_attestations')
    op.drop_index(op.f('ix_client_attestations_id'), table_name='client_attestations')
    op.drop_table('client_attestations')

    op.drop_column('users', 'device_secret_salt')

    op.drop_index(op.f('ix_exam_security_configs_exam_id'), table_name='exam_security_configs')
    op.drop_index(op.f('ix_exam_security_configs_id'), table_name='exam_security_configs')
    op.drop_table('exam_security_configs')

    op.drop_index(op.f('ix_system_settings_setting_key'), table_name='system_settings')
    op.drop_index(op.f('ix_system_settings_id'), table_name='system_settings')
    op.drop_table('system_settings')

    op.drop_column('exam_sessions', 'attestation_status')
    op.drop_column('exam_sessions', 'device_fingerprint')
    op.drop_column('exam_sessions', 'client_version')
    op.drop_column('exam_sessions', 'client_type')

    op.drop_column('exams', 'updated_at')
    op.drop_column('exams', 'require_safe_browser')
