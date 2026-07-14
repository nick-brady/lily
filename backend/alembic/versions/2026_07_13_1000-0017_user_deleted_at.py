"""user deleted_at

Self-serve account deletion anonymizes the user row in place (a PII-free
sentinel survives wherever authored content still references it — five
RESTRICT FKs make hard-deleting a parent's row impossible). `deleted_at`
marks the row disabled: `_user_from_jwt` fails closed on it, since the
30-day stateless JWTs have no revocation list.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-13 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0017"
down_revision: Union[str, Sequence[str], None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
