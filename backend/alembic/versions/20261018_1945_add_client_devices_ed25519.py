"""Thêm bảng client_devices — khoá công khai Ed25519 của thiết bị.

Thay thế mô hình khoá đối xứng: server không còn phải sinh `device_secret` và
gửi xuống client. Xem docs/PLAN.md mục 1.5.2.

Revision ID: c4d8e1f2a903
Revises: b1f3a9c47d2e
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4d8e1f2a903'
down_revision: Union[str, None] = 'b1f3a9c47d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'client_devices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.String(length=32), nullable=False),
        sa.Column('public_key', sa.String(length=128), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('client_version', sa.String(length=20), nullable=True),
        sa.Column('weak_key_storage', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'device_id', name='uq_client_device_user_device'),
    )
    op.create_index('ix_client_devices_id', 'client_devices', ['id'])
    op.create_index('ix_client_devices_user_id', 'client_devices', ['user_id'])
    op.create_index('ix_client_devices_device_id', 'client_devices', ['device_id'])
    op.create_index('idx_client_device_fingerprint', 'client_devices', ['fingerprint'])

    # Cột ghi thiết bị đã xác thực vào phiên thi. Cho phép NULL để các phiên
    # tạo trước khi có cột này vẫn dùng được.
    op.add_column('exam_sessions', sa.Column('device_id', sa.String(length=32), nullable=True))
    op.create_index('ix_exam_sessions_device_id', 'exam_sessions', ['device_id'])


def downgrade() -> None:
    op.drop_index('ix_exam_sessions_device_id', table_name='exam_sessions')
    op.drop_column('exam_sessions', 'device_id')

    op.drop_index('idx_client_device_fingerprint', table_name='client_devices')
    op.drop_index('ix_client_devices_device_id', table_name='client_devices')
    op.drop_index('ix_client_devices_user_id', table_name='client_devices')
    op.drop_index('ix_client_devices_id', table_name='client_devices')
    op.drop_table('client_devices')