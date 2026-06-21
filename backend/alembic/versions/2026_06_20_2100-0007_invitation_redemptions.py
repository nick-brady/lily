"""invitation redemptions

Adds `viewer_invitation_redemptions` so parents can see who joined through
a given invite link and when. The `redemption_count` integer on
`viewer_invitations` only ever tracked clicks, not identities.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-20 21:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "viewer_invitation_redemptions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "invitation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("viewer_invitations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "redeemed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "invitation_id", "user_id", name="uq_invitation_redemption"
        ),
    )
    op.create_index(
        "ix_invitation_redemptions_invitation",
        "viewer_invitation_redemptions",
        ["invitation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invitation_redemptions_invitation",
        table_name="viewer_invitation_redemptions",
    )
    op.drop_table("viewer_invitation_redemptions")
