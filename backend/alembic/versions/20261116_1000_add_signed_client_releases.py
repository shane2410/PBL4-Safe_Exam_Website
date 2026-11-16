"""Thêm bảng signed_client_releases và cột client_hash cho exam_sessions.

Phục vụ Phase 2: Chống crack & xác thực tính toàn vẹn SEB Client thông qua mã băm SHA-256
của các bản phát hành đã ký (allowlist release hash).

Revision ID: f3a9b5d7e821
Revises: e2f8a4c6d730
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3a9b5d7e821"
down_revision: Union[str, None] = "e2f8a4c6d730"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Bảng signed_client_releases
    op.create_table(
        "signed_client_releases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False, index=True),
        sa.Column("hash", sa.String(length=64), nullable=False, index=True),
        sa.Column("os", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("released_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("notes", sa.String(length=255), nullable=True),
    )

    # 2. Cột client_hash trong exam_sessions
    op.add_column(
        "exam_sessions",
        sa.Column("client_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exam_sessions", "client_hash")
    op.drop_table("signed_client_releases")
