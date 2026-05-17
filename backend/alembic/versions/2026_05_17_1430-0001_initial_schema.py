"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-17 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("updates")
    op.drop_table("contractions")
