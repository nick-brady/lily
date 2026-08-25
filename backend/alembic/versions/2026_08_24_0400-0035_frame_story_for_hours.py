"""the story replaces the borrowed clock card among the framed prints

The second framed print is now drawn for the frame: every moment of the
timeline — photos, milestones, short notes — wrapping the mat opening in
order, the labor clock small in the middle. The clock card fitted onto the
sheet is retired here (its renderings soft-deleted; the card template stays
in code). Catalog row note follows the registry.

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-24 04:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0035"
down_revision: Union[str, Sequence[str], None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE gift_renderings SET deleted_at = now() "
        "WHERE template_id = 'frame_hours' AND deleted_at IS NULL"
    )
    op.execute(
        "UPDATE gift_catalog_items SET template_metadata = "
        """'{"templates": ["frame_wall", "frame_story", "frame_pool"]}'::jsonb """
        "WHERE product_kind = 'framed_print'"
    )


def downgrade() -> None:
    op.execute("UPDATE gift_renderings SET deleted_at = now() WHERE template_id = 'frame_story' AND deleted_at IS NULL")
    op.execute("UPDATE gift_renderings SET deleted_at = NULL WHERE template_id = 'frame_hours'")
    op.execute(
        "UPDATE gift_catalog_items SET template_metadata = "
        """'{"templates": ["frame_wall", "frame_hours", "frame_pool"]}'::jsonb """
        "WHERE product_kind = 'framed_print'"
    )
