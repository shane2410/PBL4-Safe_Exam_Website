"""Thêm cột device_id vào client_attestations.

Ghi lại thiết bị Ed25519 nào đã xác thực cho phiên thi — hữu ích cho phúc tra
và truy vết khi một tài khoản đăng ký nhiều máy.

Revision ID: d5e7c3a9b124
Revises: c4d8e1f2a903
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd5e7c3a9b124'
down_revision: Union[str, None] = 'c4d8e1f2a903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'client_attestations', sa.Column('device_id', sa.String(length=32), nullable=True)
    )
    op.create_index(
        'idx_attestation_device', 'client_attestations', ['device_id', 'verified']
    )


def downgrade() -> None:
    op.drop_index('idx_attestation_device', table_name='client_attestations')
    op.drop_column('client_attestations', 'device_id')