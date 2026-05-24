"""drop legacy contractions + updates

Runs AFTER `scripts/migrate_to_multitenant.py` has copied the legacy data
into the new multi-tenant model. Dropping these tables is destructive; the
script writes a JSON backup to /tmp before running.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24 09:16:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS updates")
    op.execute("DROP TABLE IF EXISTS contractions")


def downgrade() -> None:
    op.create_table(
        "contractions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("start_time", sa.Text(), nullable=False),
        sa.Column("end_time", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "ignore_interval_before",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        "updates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("photo_filename", sa.Text(), nullable=True),
        sa.Column("audio_filename", sa.Text(), nullable=True),
        sa.Column("milestone", sa.Text(), nullable=True),
    )
