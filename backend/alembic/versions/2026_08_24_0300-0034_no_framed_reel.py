"""the filmstrip comes off the framed prints

The wall already hangs the day's photos around the labor; a second photo
design beside it, borrowed from the cards, told the same story worse. Its
renderings are soft-deleted so galleries stop showing them (orders keep
their FK); the catalog row's informational template list follows the code
registry.

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-24 03:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0034"
down_revision: Union[str, Sequence[str], None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE gift_renderings SET deleted_at = now() "
        "WHERE template_id = 'frame_reel' AND deleted_at IS NULL"
    )
    op.execute(
        "UPDATE gift_catalog_items SET template_metadata = "
        """'{"templates": ["frame_wall", "frame_hours", "frame_pool"]}'::jsonb """
        "WHERE product_kind = 'framed_print'"
    )


def downgrade() -> None:
    op.execute("UPDATE gift_renderings SET deleted_at = NULL WHERE template_id = 'frame_reel'")
    op.execute(
        "UPDATE gift_catalog_items SET template_metadata = "
        """'{"templates": ["frame_wall", "frame_hours", "frame_reel", "frame_pool"]}'::jsonb """
        "WHERE product_kind = 'framed_print'"
    )
