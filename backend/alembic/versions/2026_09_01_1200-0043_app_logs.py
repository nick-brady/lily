"""app logs and service heartbeats

Production had no error visibility: the web process configured no logging,
so INFO was dropped and the rare warning went to journald with nothing to
say which request it belonged to. `app_logs` holds thirty days of records
at INFO and above from both processes, redacted, so the admin site can show
them. `service_heartbeats` lets `/health` say whether the worker is alive.

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-01 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0043"
down_revision: Union[str, Sequence[str], None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "logged_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("service", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("logger", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exception", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_app_logs_logged_at", "app_logs", ["logged_at"])
    op.create_index("ix_app_logs_fingerprint", "app_logs", ["fingerprint"])

    op.create_table(
        "service_heartbeats",
        sa.Column("service", sa.Text(), primary_key=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("service_heartbeats")
    op.drop_index("ix_app_logs_fingerprint", table_name="app_logs")
    op.drop_index("ix_app_logs_logged_at", table_name="app_logs")
    op.drop_table("app_logs")
