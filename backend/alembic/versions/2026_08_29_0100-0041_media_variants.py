"""smaller copies of a photo, and the worker's claim on making them

Every image was served at upload resolution however small it was drawn — a
4000px photo to fill a 57px tile. A photo now gets a 1600px display copy and
a 320px thumbnail, made after upload by the media worker.

The keys are columns rather than a path convention because the worker makes
them *later*: "is it ready yet?" is a live question on every image request,
and a column answers it for free where a bucket lookup costs a round trip.
Null means not ready, and every reader falls back to the original — which is
what makes this safe before a single variant exists.

`variants_attempted_at` lets the worker claim a row in one short statement
and commit before it touches S3. `variants_error` retires a file Pillow
can't read instead of retrying it forever.

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-29 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0041"
down_revision: Union[str, Sequence[str], None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("media_assets", sa.Column("display_s3_key", sa.Text(), nullable=True))
    op.add_column("media_assets", sa.Column("thumbnail_s3_key", sa.Text(), nullable=True))
    op.add_column(
        "media_assets",
        sa.Column("variants_attempted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("media_assets", sa.Column("variants_error", sa.Text(), nullable=True))
    # The worker's queue, and only ever that: photos still waiting for their
    # copies. Partial so it stays the size of the backlog rather than the
    # size of the library.
    op.create_index(
        "ix_media_assets_variants_pending",
        "media_assets",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text(
            "kind = 'photo' AND archived_at IS NULL "
            "AND display_s3_key IS NULL AND variants_error IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_media_assets_variants_pending", table_name="media_assets")
    op.drop_column("media_assets", "variants_error")
    op.drop_column("media_assets", "variants_attempted_at")
    op.drop_column("media_assets", "thumbnail_s3_key")
    op.drop_column("media_assets", "display_s3_key")
