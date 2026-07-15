"""analytics: last_seen_at, signup attribution, page_visits

Pre-distribution instrumentation, all self-hosted. Three additions:

- `users.last_seen_at` — bumped (throttled) on authenticated requests so
  DAU/WAU and "did shared-in viewers come back" are answerable at all.
- `users.signup_*` — first-touch attribution (?ref= / utm params captured
  on the landing page, attached at signup). Set once at user creation,
  never overwritten: "which post did this signup come from" can't be
  reconstructed after the fact.
- `page_visits` — anonymous pre-signup traffic, the one thing the rest of
  the schema can't see. Deliberately stores NO IP address (cookieless,
  bannerless posture); nginx rate-limits the public insert instead.

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-15 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("signup_ref", sa.Text, nullable=True))
    op.add_column("users", sa.Column("signup_utm_source", sa.Text, nullable=True))
    op.add_column("users", sa.Column("signup_utm_medium", sa.Text, nullable=True))
    op.add_column("users", sa.Column("signup_utm_campaign", sa.Text, nullable=True))

    op.create_table(
        "page_visits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("referrer", sa.Text, nullable=True),
        sa.Column("ref", sa.Text, nullable=True),
        sa.Column("utm_source", sa.Text, nullable=True),
        sa.Column("utm_medium", sa.Text, nullable=True),
        sa.Column("utm_campaign", sa.Text, nullable=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_agent", sa.Text, nullable=True),
    )
    op.create_index("ix_page_visits_occurred_at", "page_visits", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_page_visits_occurred_at", table_name="page_visits")
    op.drop_table("page_visits")
    op.drop_column("users", "signup_utm_campaign")
    op.drop_column("users", "signup_utm_medium")
    op.drop_column("users", "signup_utm_source")
    op.drop_column("users", "signup_ref")
    op.drop_column("users", "last_seen_at")
