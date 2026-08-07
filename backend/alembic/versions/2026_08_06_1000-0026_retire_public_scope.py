"""retire the public audience scope

A birth page is private. `public` meant "any signed-in person holding the
link can see this, invited or not" — a tier that only ever served people
with no relationship to the family — and it was the DEFAULT, so in practice
every post ever made landed in it (124 of 124 in production at the time of
writing). Everything moves to `group_targeted`, the Family tier.

The enum VALUE stays. Dropping a value from a postgres enum needs a type
rewrite, and a rewrite of `timeline_events` queues behind the SSE streams'
long-lived transactions — which is how the site wedged on 2026-07-19
(migration 0019). `family_viewer` is still granted `public` in
`visible_scopes_for_role`, so anything the backfill misses stays visible to
the family instead of vanishing.

On locking: the UPDATE takes ordinary row locks. The `SET DEFAULT` is DDL
and does briefly want ACCESS EXCLUSIVE — but it's a catalog-only change
with no table rewrite, so it's milliseconds once it has the lock, and the
deploy role restarts the app first to clear idle-in-transaction streams and
runs with `lock_timeout=10s` (see deploy/roles/app/tasks/main.yml). Worst
case this migration fails fast and the deploy stops; it cannot hang prod.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-06 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0026"
down_revision: Union[str, Sequence[str], None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE timeline_events
           SET audience_scope = 'group_targeted'
         WHERE audience_scope = 'public'
        """
    )
    op.execute(
        "ALTER TABLE timeline_events "
        "ALTER COLUMN audience_scope SET DEFAULT 'group_targeted'"
    )


def downgrade() -> None:
    """Restores the column default only.

    The backfill is not reversible: `public` and `group_targeted` rows are
    indistinguishable afterwards, so putting every one of them back to
    `public` would re-widen posts that were deliberately family-only. If
    this needs undoing, the audience of each row is a product decision, not
    a migration.
    """
    op.execute(
        "ALTER TABLE timeline_events "
        "ALTER COLUMN audience_scope SET DEFAULT 'public'"
    )
