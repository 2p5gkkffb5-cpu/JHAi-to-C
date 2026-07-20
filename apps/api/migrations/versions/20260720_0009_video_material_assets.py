"""Allow uploaded video materials.

Revision ID: 20260720_0009
Revises: 20260717_0008
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0009"
down_revision: str | None = "20260717_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("uploaded_assets") as batch_op:
        batch_op.drop_constraint("ck_uploaded_assets_asset_type", type_="check")
        batch_op.create_check_constraint(
            "ck_uploaded_assets_asset_type",
            "asset_type IN ('image', 'video')",
        )


def downgrade() -> None:
    video_assets = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM uploaded_assets WHERE asset_type = 'video'")
    ).scalar_one()
    if video_assets:
        raise RuntimeError("video_material_assets_downgrade_blocked: video assets still exist")

    with op.batch_alter_table("uploaded_assets") as batch_op:
        batch_op.drop_constraint("ck_uploaded_assets_asset_type", type_="check")
        batch_op.create_check_constraint(
            "ck_uploaded_assets_asset_type",
            "asset_type IN ('image')",
        )
