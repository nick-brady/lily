"""per-slot photo choices for the filmstrip designs

The reel templates carry several photos, sampled evenly across the timeline
with no way to disagree with any one of them. The single-photo designs got an
override in 0027; this is the same idea per slot — a JSONB map of slot index
("0".."3") to the chosen media id, empty meaning every slot stays on auto.

A map rather than four columns because the slot count is the template's
business (the mug reel holds four, the card three), and rather than reusing
photo_media_id because "the photo" and "the photo in slot 2" are different
statements.

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-23 02:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0031"
down_revision: Union[str, Sequence[str], None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_renderings",
        sa.Column("photo_slots", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("gift_renderings", "photo_slots")
