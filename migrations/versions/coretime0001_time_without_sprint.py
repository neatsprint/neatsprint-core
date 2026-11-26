"""Add the time-without-sprint tenant setting.

Revision ID: coretime0001
Revises: corerls0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "coretime0001"
down_revision = "corerls0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column(
            "allow_time_without_sprint",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_settings", "allow_time_without_sprint")
