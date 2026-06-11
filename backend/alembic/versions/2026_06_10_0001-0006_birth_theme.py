"""birth theme

Adds a `theme` column to the `births` table so families can personalise
the visual identity of their birth page during setup.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-10 00:01:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "births",
        sa.Column(
            "theme",
            sa.Text,
            nullable=False,
            server_default="lily",
        ),
    )


def downgrade() -> None:
    op.drop_column("births", "theme")
