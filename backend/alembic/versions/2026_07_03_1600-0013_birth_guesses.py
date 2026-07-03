"""birth guesses

The family pool becomes a first-class table: one row per guess of the
baby's weight/length, per-user when the guesser has an account
(`user_id` + partial unique), name-only for imported/legacy entries
(`user_id` NULL).

Backfills from the short-lived `births.predictions` JSONB (migration 0012,
never had an API) and then drops that column — `birth_guesses` is the single
source of truth for both the leaderboard and the pool gift artwork. The
actual measurements stay on `births.child_weight_lbs / child_length_in`.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-03 16:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "birth_guesses",
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
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("weight_lbs", sa.Float, nullable=True),
        sa.Column("length_in", sa.Float, nullable=True),
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
    op.create_index("ix_birth_guesses_birth", "birth_guesses", ["birth_id"])
    # one guess per signed-in user per birth; name-only rows are exempt
    op.create_index(
        "uq_birth_guesses_birth_user",
        "birth_guesses",
        ["birth_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    # carry over anything seeded into births.predictions (name-only rows)
    op.execute(
        """
        INSERT INTO birth_guesses (birth_id, display_name, weight_lbs, length_in)
        SELECT b.id,
               g->>'name',
               (g->>'weight_lbs')::float,
               (g->>'length_in')::float
        FROM births b, jsonb_array_elements(b.predictions) AS g
        WHERE b.predictions IS NOT NULL
          AND COALESCE(g->>'name', '') <> ''
        """
    )
    op.drop_column("births", "predictions")


def downgrade() -> None:
    op.add_column(
        "births", sa.Column("predictions", postgresql.JSONB(), nullable=True)
    )
    op.execute(
        """
        UPDATE births b SET predictions = sub.preds
        FROM (
            SELECT birth_id,
                   jsonb_agg(jsonb_build_object(
                       'name', display_name,
                       'weight_lbs', weight_lbs,
                       'length_in', length_in
                   )) AS preds
            FROM birth_guesses GROUP BY birth_id
        ) sub
        WHERE b.id = sub.birth_id
        """
    )
    op.drop_index("uq_birth_guesses_birth_user", table_name="birth_guesses")
    op.drop_index("ix_birth_guesses_birth", table_name="birth_guesses")
    op.drop_table("birth_guesses")
