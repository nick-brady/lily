"""the wall leads the framed prints

Informational only — which templates a product carries is the code
registry's business (`gift_templates.for_product`), and this keeps the
catalog row's note in step with it. The wall is the design drawn for the
frame rather than borrowed from the cards: the labor as a border around the
mat opening, the day's photos hung inside it.

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-24 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0033"
down_revision: Union[str, Sequence[str], None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE gift_catalog_items SET template_metadata = "
        """'{"templates": ["frame_wall", "frame_hours", "frame_reel", "frame_pool"]}'::jsonb """
        "WHERE product_kind = 'framed_print'"
    )


def downgrade() -> None:
    op.execute("UPDATE gift_renderings SET deleted_at = now() WHERE template_id = 'frame_wall' AND deleted_at IS NULL")
    op.execute(
        "UPDATE gift_catalog_items SET template_metadata = "
        """'{"templates": ["frame_hours", "frame_reel", "frame_pool"]}'::jsonb """
        "WHERE product_kind = 'framed_print'"
    )
