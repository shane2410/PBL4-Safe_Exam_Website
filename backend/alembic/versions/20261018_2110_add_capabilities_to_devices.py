"""Thêm cột capabilities / unsupported vào client_devices.

GV cần biết máy thí sinh có thực sự được bảo vệ đầy đủ không. Ví dụ trên
Wayland, cơ chế phát hiện chuyển cửa sổ không hoạt động — nếu chỉ ghi log cục bộ
thì giảng viên không có cách nào thấy, và việc "báo cáo trung thực" trở nên vô
nghĩa.

Revision ID: e2f8a4c6d730
Revises: d5e7c3a9b124
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e2f8a4c6d730'
down_revision: Union[str, None] = 'd5e7c3a9b124'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'client_devices', sa.Column('capabilities', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'client_devices', sa.Column('unsupported', sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('client_devices', 'unsupported')
    op.drop_column('client_devices', 'capabilities')