"""guess pool v2

The pool grows up: a due date on births (drives the 36-week guess-edit
lock), a parent toggle for gender guessing plus the actual sex recorded at
settle, and two new guess dimensions — sex and arrival date.

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-27 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0025"
down_revision: Union[str, Sequence[str], None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("births", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column(
        "births",
        sa.Column(
            "gender_pool_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("births", sa.Column("child_sex", sa.Text(), nullable=True))
    op.add_column("birth_guesses", sa.Column("sex_guess", sa.Text(), nullable=True))
    op.add_column("birth_guesses", sa.Column("date_guess", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("birth_guesses", "date_guess")
    op.drop_column("birth_guesses", "sex_guess")
    op.drop_column("births", "child_sex")
    op.drop_column("births", "gender_pool_enabled")
    op.drop_column("births", "due_date")
