"""the wooden ornament joins the shelf

Her name and the hour she arrived on a wooden oval, for the first tree
she'll see. $24 against $8.21 + ~$5 to make and ship. Oval only for now: the
other five die-cut shapes each need a design fitted to their silhouette.

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-25 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0036"
down_revision: Union[str, Sequence[str], None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO gift_catalog_items "
        "(kind, product_kind, display_name, base_price_cents, fulfillment_partner, "
        " template_metadata, surfaces_in, is_active, sort_order) "
        "SELECT 'physical', 'ornament', 'Wooden Ornament', 2400, 'printful', "
        """ '{"templates": ["ornament_oval"]}'::jsonb, """
        """ '["day_two_prompt", "on_page_catalog"]'::jsonb, true, 18 """
        "WHERE NOT EXISTS (SELECT 1 FROM gift_catalog_items WHERE product_kind = 'ornament')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM gift_renderings WHERE template_id = 'ornament_oval'")
    op.execute("DELETE FROM gift_catalog_items WHERE product_kind = 'ornament'")
