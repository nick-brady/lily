"""the photo book joins the shelf

A hardcover 8×8 of the whole story — the clock, the pool, the day's photos
hung two to four to a page with the family's notes between, the milestones,
two pages for a pen, and a closing. $49 against $11.23 + ~$7.50 to make and
ship. Twenty-four pages, matte by default.

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-25 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0037"
down_revision: Union[str, Sequence[str], None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO gift_catalog_items "
        "(kind, product_kind, display_name, base_price_cents, fulfillment_partner, "
        " template_metadata, surfaces_in, is_active, sort_order) "
        "SELECT 'physical', 'photo_book', 'The Day, as a Book', 4900, 'printful', "
        """ '{"templates": ["book_8x8"]}'::jsonb, """
        """ '["day_two_prompt", "on_page_catalog"]'::jsonb, true, 16 """
        "WHERE NOT EXISTS (SELECT 1 FROM gift_catalog_items WHERE product_kind = 'photo_book')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM gift_renderings WHERE template_id = 'book_8x8'")
    op.execute("DELETE FROM gift_catalog_items WHERE product_kind = 'photo_book'")
