"""one contraction running at a time, per birth

Both parents watch the same page during labour and neither knows who is going
to press the button, so sometimes they both do within the same second. Start
was a blind insert, so that made two open contractions — and the second one is
not a harmless duplicate. The button stops the older, flips back to STOP for
the other, and that one can never be stopped through the UI again. With no
duration it vanishes from the keepsake's count, while the CSV export still
measures the following interval from it.

The route now hands a second tapper the contraction that is already running.
This index is what makes that an invariant rather than a convention.

Revision ID: 0042
Revises: 0041
Create Date: 2026-08-30 01:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0042"
down_revision: Union[str, Sequence[str], None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OPEN = (
    "event_type = 'contraction' AND deleted_at IS NULL "
    "AND payload->>'end_time' IS NULL"
)


def upgrade() -> None:
    # A birth that already has two open contractions would fail the index with
    # a message about a duplicate key and nothing about what to do. Say it
    # plainly instead, and leave the data alone for a human to look at.
    conn = op.get_bind()
    offenders = conn.execute(
        sa.text(
            f"SELECT birth_id, count(*) FROM timeline_events WHERE {_OPEN} "
            "GROUP BY birth_id HAVING count(*) > 1"
        )
    ).all()
    if offenders:
        listed = ", ".join(f"{row[0]} ({row[1]} open)" for row in offenders)
        raise RuntimeError(
            "These births have more than one contraction still running, so the "
            f"index can't be created: {listed}. Stop or delete the extras "
            "first — the newest is almost always the accidental one."
        )
    op.create_index(
        "uq_timeline_events_one_open_contraction",
        "timeline_events",
        ["birth_id"],
        unique=True,
        postgresql_where=sa.text(_OPEN),
    )


def downgrade() -> None:
    op.drop_index("uq_timeline_events_one_open_contraction", table_name="timeline_events")
