"""viewer invitations

Adds the `viewer_invitations` table. Tokens are stored as salted SHA-256
hashes; only the recipient (and the family member who created it) ever
sees the plaintext secret.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-24 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `family_role` is owned by migration 0002 — referencing it here with
    # `create_type=False` prevents Alembic from re-emitting CREATE TYPE.
    family_role = postgresql.ENUM(
        "owner",
        "co_parent",
        "family_viewer",
        name="family_role",
        create_type=False,
    )
    op.create_table(
        "viewer_invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "birth_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("births.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "role",
            family_role,
            nullable=False,
            server_default="family_viewer",
        ),
        sa.Column("salt", sa.Text, nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("display_name_hint", sa.Text, nullable=True),
        sa.Column("email_hint", sa.Text, nullable=True),
        sa.Column("phone_hint", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redemption_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_viewer_invitations_birth", "viewer_invitations", ["birth_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_viewer_invitations_birth", table_name="viewer_invitations")
    op.drop_table("viewer_invitations")
