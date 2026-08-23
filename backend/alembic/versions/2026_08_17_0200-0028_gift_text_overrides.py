"""per-design text overrides

The name, and one optional line of the parent's own, per design. Same shape as
the photo choice in 0027: you're editing this mug, not every keepsake.

Deliberately narrow. Everything else on a keepsake is derived from the birth —
"97 CONTRACTIONS · 26H 56M" is a fact, and making it a text field invites
someone to type a number that isn't true, which is the one thing these are for.
So the derived lines stay derived, the name can be shortened to the one people
actually use, and anything else a parent wants to say goes on a line that was
always theirs.

JSONB rather than columns: the set of editable keys is per template and will
grow, and a migration per new slot would be silly.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-17 02:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0028"
down_revision: Union[str, Sequence[str], None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_renderings",
        sa.Column(
            "text_overrides",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("gift_renderings", "text_overrides")
