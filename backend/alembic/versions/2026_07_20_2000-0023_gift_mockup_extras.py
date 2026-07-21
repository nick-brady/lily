"""gift mockup extras

Adds `mockup_extras` to `gift_renderings` — the extra angle/view mockups
Printful returns alongside the primary one (e.g. a mug's handle-from-left
shot), stored as a JSONB list of {"title", "s3_key"}.

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-20 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_renderings",
        sa.Column(
            "mockup_extras",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("gift_renderings", "mockup_extras")
