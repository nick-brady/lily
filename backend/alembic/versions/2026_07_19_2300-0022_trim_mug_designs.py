"""trim the mug lineup to three designs

Curation call (2026-07-19): the Birth Story Mug keeps the labor clock
(mug_hours), the filmstrip (mug_reel), and the family-pool leaderboard
(mug_pool — the winner's trophy); mug_hours_photo and mug_horizon are
retired. Three beautiful items reads "curated keepsakes";
a stack of five reads "catalog". The retired templates are removed from
the code registry; this migration soft-deletes their existing renderings
so already-generated designs disappear from galleries too (soft — orders
referencing them keep their FK, and downgrade can restore).

Also refreshes the mug row's informational template_metadata, which still
carried the original seed names.

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-19 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RETIRED = ("mug_hours_photo", "mug_horizon")


def upgrade() -> None:
    op.execute(
        "UPDATE gift_renderings SET deleted_at = now() "
        f"WHERE template_id IN {_RETIRED!r} AND deleted_at IS NULL"
    )
    op.execute(
        "UPDATE gift_catalog_items "
        """SET template_metadata = '{"templates": ["mug_hours", "mug_pool", "mug_reel"]}'::jsonb """
        "WHERE product_kind = 'mug'"
    )


def downgrade() -> None:
    # restore only rows this migration retired (identifiable by template id;
    # organically deleted rows of other templates are untouched)
    op.execute(
        "UPDATE gift_renderings SET deleted_at = NULL "
        f"WHERE template_id IN {_RETIRED!r}"
    )
