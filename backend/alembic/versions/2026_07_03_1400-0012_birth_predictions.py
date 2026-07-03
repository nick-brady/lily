"""birth predictions + measurements

Adds the family prediction pool and the actual birth measurements to
`births`, so the pool leaderboard (currently a hardcoded frontend component)
has a real home and the gift artwork can render it.

`predictions` is a JSONB list of {"name", "weight_lbs", "length_in"} —
weights as decimal pounds, lengths as decimal inches, either nullable.
Matches the shape of frontend/src/components/Predictions.jsx.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-03 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("births", sa.Column("predictions", JSONB(), nullable=True))
    op.add_column("births", sa.Column("child_weight_lbs", sa.Float(), nullable=True))
    op.add_column("births", sa.Column("child_length_in", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("births", "child_length_in")
    op.drop_column("births", "child_weight_lbs")
    op.drop_column("births", "predictions")
