"""gift generation

Adds `gift_catalog_items` (purchasable products) and `gift_renderings`
(generated artwork per birth × catalog item × template), plus the
`gift_kind` and `gift_rendering_status` enums. Seeds three catalog rows:
a mug, announcement cards, and a 5-year storage gift.

Payment / order / shipment tables are intentionally deferred to later
phases — see Lily-Product-Spec.md.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-27 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    gift_kind = postgresql.ENUM(
        "physical",
        "storage_gift",
        "free_digital",
        name="gift_kind",
    )
    gift_rendering_status = postgresql.ENUM(
        "pending",
        "ready",
        "failed",
        name="gift_rendering_status",
    )
    gift_kind.create(op.get_bind())
    gift_rendering_status.create(op.get_bind())

    op.create_table(
        "gift_catalog_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "kind",
            postgresql.ENUM(name="gift_kind", create_type=False),
            nullable=False,
        ),
        sa.Column("product_kind", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column(
            "base_price_cents", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("fulfillment_partner", sa.Text, nullable=True),
        sa.Column("fulfillment_sku", sa.Text, nullable=True),
        sa.Column(
            "template_metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("storage_years_granted", sa.Integer, nullable=True),
        sa.Column(
            "surfaces_in",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "gift_renderings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "birth_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("births.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "gift_catalog_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gift_catalog_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("template_id", sa.Text, nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="gift_rendering_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("artwork_s3_key", sa.Text, nullable=True),
        sa.Column(
            "rendering_metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column(
            "is_visible_to_viewers",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_gift_renderings_birth", "gift_renderings", ["birth_id"])
    op.create_index(
        "uq_gift_renderings_birth_item_template",
        "gift_renderings",
        ["birth_id", "gift_catalog_item_id", "template_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Seed the starter catalog. `template_metadata.templates` lists the
    # template ids (gift_templates.py) valid for each product.
    catalog = sa.table(
        "gift_catalog_items",
        sa.column("kind", postgresql.ENUM(name="gift_kind", create_type=False)),
        sa.column("product_kind", sa.Text),
        sa.column("display_name", sa.Text),
        sa.column("base_price_cents", sa.Integer),
        sa.column("fulfillment_partner", sa.Text),
        sa.column("template_metadata", postgresql.JSONB),
        sa.column("storage_years_granted", sa.Integer),
        sa.column("surfaces_in", postgresql.JSONB),
    )
    op.bulk_insert(
        catalog,
        [
            {
                "kind": "physical",
                "product_kind": "mug",
                "display_name": "Birth Story Mug",
                "base_price_cents": 1800,
                "fulfillment_partner": "gelato",
                "template_metadata": {"templates": ["mug_pattern", "mug_stats"]},
                "storage_years_granted": None,
                "surfaces_in": ["day_two_prompt", "on_page_catalog"],
            },
            {
                "kind": "physical",
                "product_kind": "birth_announcement_cards",
                "display_name": "Birth Announcement Cards",
                "base_price_cents": 2500,
                "fulfillment_partner": "gelato",
                "template_metadata": {"templates": ["card_classic"]},
                "storage_years_granted": None,
                "surfaces_in": ["day_two_prompt", "on_page_catalog"],
            },
            {
                "kind": "storage_gift",
                "product_kind": "storage_5yr",
                "display_name": "5 Years of Storage",
                "base_price_cents": 1500,
                "fulfillment_partner": None,
                "template_metadata": {},
                "storage_years_granted": 5,
                "surfaces_in": ["day_two_prompt", "parent_dashboard_post_birth"],
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "uq_gift_renderings_birth_item_template", table_name="gift_renderings"
    )
    op.drop_index("ix_gift_renderings_birth", table_name="gift_renderings")
    op.drop_table("gift_renderings")
    op.drop_table("gift_catalog_items")
    postgresql.ENUM(name="gift_rendering_status").drop(op.get_bind())
    postgresql.ENUM(name="gift_kind").drop(op.get_bind())
