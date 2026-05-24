"""reactions + comments

Adds `timeline_event_reactions` and `timeline_event_comments`. Reactions
are free-tier (anyone authed); comments require `birth.is_unlocked`,
which is enforced in the route layer (the model doesn't need to know).

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-24 11:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the new enum type explicitly, then reference it with
    # create_type=False on every column so Alembic doesn't try to
    # CREATE TYPE again (the same pattern 0002 uses for its enums).
    reaction_kind = postgresql.ENUM(
        "love", "wow", "pray", name="reaction_kind", create_type=False
    )
    reaction_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "timeline_event_reactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("timeline_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            reaction_kind,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "event_id",
            "user_id",
            "kind",
            name="uq_timeline_event_reactions_event_user_kind",
        ),
    )
    op.create_index(
        "ix_timeline_event_reactions_event",
        "timeline_event_reactions",
        ["event_id"],
    )

    op.create_table(
        "timeline_event_comments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("timeline_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_timeline_event_comments_event",
        "timeline_event_comments",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_timeline_event_comments_event", table_name="timeline_event_comments")
    op.drop_table("timeline_event_comments")
    op.drop_index("ix_timeline_event_reactions_event", table_name="timeline_event_reactions")
    op.drop_table("timeline_event_reactions")
    postgresql.ENUM(name="reaction_kind").drop(op.get_bind(), checkfirst=True)
