"""framed prints in, announcement cards out

The cards were never a product. No fulfillment mapping existed for them, so
they sat in the gallery as "$25.00 coming soon" under the mug — a placeholder
wearing a price tag. A framed print is a real one: the same three designs as
the mug on a matted 12×16 poster, at roughly three and a half times the mug's
margin, and the thing people actually hang in a nursery.

The cards row is deactivated rather than deleted (orders reference catalog
rows) and its renderings are soft-deleted so galleries stop showing them.
The card *templates* stay in code: three of them are what the framed prints
draw.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-24 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0032"
down_revision: Union[str, Sequence[str], None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE gift_renderings SET deleted_at = now() "
        "WHERE deleted_at IS NULL AND gift_catalog_item_id IN "
        "(SELECT id FROM gift_catalog_items WHERE product_kind = 'birth_announcement_cards')"
    )
    op.execute(
        "UPDATE gift_catalog_items SET is_active = false "
        "WHERE product_kind = 'birth_announcement_cards'"
    )
    op.execute(
        "INSERT INTO gift_catalog_items "
        "(kind, product_kind, display_name, base_price_cents, fulfillment_partner, "
        " template_metadata, surfaces_in, is_active, sort_order) "
        "SELECT 'physical', 'framed_print', 'Framed Print', 7900, 'printful', "
        """ '{"templates": ["frame_hours", "frame_reel", "frame_pool"]}'::jsonb, """
        """ '["day_two_prompt", "on_page_catalog"]'::jsonb, true, 15 """
        "WHERE NOT EXISTS (SELECT 1 FROM gift_catalog_items WHERE product_kind = 'framed_print')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM gift_renderings WHERE template_id LIKE 'frame_%'")
    op.execute("DELETE FROM gift_catalog_items WHERE product_kind = 'framed_print'")
    op.execute(
        "UPDATE gift_catalog_items SET is_active = true "
        "WHERE product_kind = 'birth_announcement_cards'"
    )
    op.execute(
        "UPDATE gift_renderings SET deleted_at = NULL "
        "WHERE gift_catalog_item_id IN "
        "(SELECT id FROM gift_catalog_items WHERE product_kind = 'birth_announcement_cards')"
    )
