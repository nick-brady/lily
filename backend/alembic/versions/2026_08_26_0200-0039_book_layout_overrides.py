"""the parent's own arrangement of the book's pages

A JSONB map on the rendering — {"pages": [...]} for the book's middle section:
gallery pages of one to four photos, notes pages and ruled pages, added,
removed and reordered in the editor. Empty means the automatic plan, so every
existing rendering keeps behaving exactly as it does now.

Revision ID: 0039
Revises: 0038
Create Date: 2026-08-26 02:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0039"
down_revision: Union[str, Sequence[str], None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_renderings", sa.Column("layout_overrides", JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("gift_renderings", "layout_overrides")
