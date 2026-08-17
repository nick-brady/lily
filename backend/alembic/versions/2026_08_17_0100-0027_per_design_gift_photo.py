"""per-design gift photo

The photo on a keepsake was chosen for you and could not be changed:
`_select_hero_photo` picked the first viewer-visible photo at or after the
birth and that was the end of it. These two columns let a parent override the
guess on one design without touching any other — you're editing this mug, not
every keepsake at once.

Three states, which is what "guess for me, but let me override" requires:

    photo_media_id NULL, photo_removed false  → auto (today's behaviour)
    photo_media_id set                        → this photo
    photo_removed true                        → no photo, deliberately

Auto is not the same as removed. An unset choice means "you decide"; a removed
one means "I decided, and the answer is none". Collapsing them into a single
nullable column would make "take the photo off" indistinguishable from "never
chose", and the next render would helpfully put a photo back.

Both columns are nullable/defaulted, so every existing rendering keeps
rendering exactly as it does now.

On locking: two ADD COLUMNs with a constant default and a new FK. Postgres 11+
fills the default in the catalog rather than rewriting the table, so this is
milliseconds once it has the lock. The FK takes a SHARE ROW EXCLUSIVE on
`media_assets`, which nothing long-lived holds.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-17 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "0027"
down_revision: Union[str, Sequence[str], None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_renderings",
        sa.Column("photo_media_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "gift_renderings",
        sa.Column(
            "photo_removed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_foreign_key(
        "gift_renderings_photo_media_id_fkey",
        "gift_renderings",
        "media_assets",
        ["photo_media_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "gift_renderings_photo_media_id_fkey", "gift_renderings", type_="foreignkey"
    )
    op.drop_column("gift_renderings", "photo_removed")
    op.drop_column("gift_renderings", "photo_media_id")
