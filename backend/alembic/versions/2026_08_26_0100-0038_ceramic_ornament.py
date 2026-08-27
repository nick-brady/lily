"""the ornament becomes a ceramic photo circle

The wooden oval carried the labor dial; at three inches a photo of the baby
is the better ornament, and ceramic takes one. Renderings of the wooden design
are soft-deleted (orders keep their FK); the catalog row is renamed and its
template list follows the registry. Price unchanged.

Revision ID: 0038
Revises: 0037
Create Date: 2026-08-26 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0038"
down_revision: Union[str, Sequence[str], None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE gift_renderings SET deleted_at = now() WHERE template_id = 'ornament_oval' AND deleted_at IS NULL")
    op.execute(
        "UPDATE gift_catalog_items SET display_name = 'Ceramic Ornament', "
        """template_metadata = '{"templates": ["ornament_circle"]}'::jsonb """
        "WHERE product_kind = 'ornament'"
    )


def downgrade() -> None:
    op.execute("UPDATE gift_renderings SET deleted_at = now() WHERE template_id = 'ornament_circle' AND deleted_at IS NULL")
    op.execute("UPDATE gift_renderings SET deleted_at = NULL WHERE template_id = 'ornament_oval'")
    op.execute(
        "UPDATE gift_catalog_items SET display_name = 'Wooden Ornament', "
        """template_metadata = '{"templates": ["ornament_oval"]}'::jsonb """
        "WHERE product_kind = 'ornament'"
    )
