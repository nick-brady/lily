"""invitation plaintext token

Stores the plaintext invite token so parents can re-copy a link to
re-share it. A deliberate exception to the hash-only rule: a viewer link
is low-stakes (multi-use, expiring, revocable, view-only) unlike auth
magic links. Null for invitations created before this column existed.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-20 21:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "viewer_invitations",
        sa.Column("token", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("viewer_invitations", "token")
