"""notify phone opt-in

Adds `notify_phone` + `notify_phone_opted_in_at` to `users` — the explicit
birth-events-only text opt-in from the 2026-07-23 auth decision (identity is
email; phone is a notification opt-in). `notify_phone_opted_in_at` doubles as
the TCPA consent record.

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-23 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0024"
down_revision: Union[str, Sequence[str], None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("notify_phone", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "notify_phone_opted_in_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "notify_phone_opted_in_at")
    op.drop_column("users", "notify_phone")
