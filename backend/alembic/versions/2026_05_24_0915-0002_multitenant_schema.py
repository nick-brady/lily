"""multitenant schema

Adds the multi-tenant domain model (families, users, family_memberships, births,
timeline_events, media_assets, auth_challenges). Leaves the legacy
`contractions` and `updates` tables in place; revision 0003 drops them
after the data migration script has copied them into the new model.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-24 09:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FAMILY_ROLE_VALUES = ("owner", "co_parent", "family_viewer")
BIRTH_STATUS_VALUES = ("preparing", "in_labor", "born", "archived")
BIRTH_STORAGE_TIER_VALUES = ("active", "cold", "archived")
TIMELINE_EVENT_TYPE_VALUES = (
    "contraction",
    "milestone",
    "text_note",
    "photo",
    "video",
    "voice_memo",
)
AUDIENCE_SCOPE_VALUES = ("public", "group_targeted", "parents_only")
MEDIA_KIND_VALUES = ("photo", "video", "voice_memo")
MEDIA_STORAGE_TIER_VALUES = ("hot", "cold")
AUTH_IDENTIFIER_KIND_VALUES = ("email", "phone")


def upgrade() -> None:
    family_role = postgresql.ENUM(*FAMILY_ROLE_VALUES, name="family_role", create_type=False)
    birth_status = postgresql.ENUM(*BIRTH_STATUS_VALUES, name="birth_status", create_type=False)
    birth_storage_tier = postgresql.ENUM(
        *BIRTH_STORAGE_TIER_VALUES, name="birth_storage_tier", create_type=False
    )
    timeline_event_type = postgresql.ENUM(
        *TIMELINE_EVENT_TYPE_VALUES, name="timeline_event_type", create_type=False
    )
    audience_scope = postgresql.ENUM(
        *AUDIENCE_SCOPE_VALUES, name="audience_scope", create_type=False
    )
    media_kind = postgresql.ENUM(*MEDIA_KIND_VALUES, name="media_kind", create_type=False)
    media_storage_tier = postgresql.ENUM(
        *MEDIA_STORAGE_TIER_VALUES, name="media_storage_tier", create_type=False
    )
    auth_identifier_kind = postgresql.ENUM(
        *AUTH_IDENTIFIER_KIND_VALUES, name="auth_identifier_kind", create_type=False
    )

    bind = op.get_bind()
    family_role.create(bind, checkfirst=True)
    birth_status.create(bind, checkfirst=True)
    birth_storage_tier.create(bind, checkfirst=True)
    timeline_event_type.create(bind, checkfirst=True)
    audience_scope.create(bind, checkfirst=True)
    media_kind.create(bind, checkfirst=True)
    media_storage_tier.create(bind, checkfirst=True)
    auth_identifier_kind.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL",
            name="ck_users_email_or_phone",
        ),
    )
    op.create_index(
        "ix_users_email_unique",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "ix_users_phone_unique",
        "users",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )

    op.create_table(
        "families",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "primary_owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("display_name", sa.Text(), nullable=False),
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

    op.create_table(
        "family_memberships",
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
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", family_role, nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("family_id", "user_id", name="uq_family_memberships_family_user"),
    )

    op.create_table(
        "births",
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
        sa.Column("child_name", sa.Text(), nullable=True),
        sa.Column("child_dob", sa.DateTime(timezone=True), nullable=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("status", birth_status, nullable=False, server_default="preparing"),
        sa.Column("birth_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("birth_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "storage_tier",
            birth_storage_tier,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "is_unlocked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "unlocked_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_locked_to_invited",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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

    op.create_table(
        "timeline_events",
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
        sa.Column("event_type", timeline_event_type, nullable=False),
        sa.Column("sequence_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "posted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "audience_scope",
            audience_scope,
            nullable=False,
            server_default="public",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("birth_id", "sequence_id", name="uq_timeline_events_birth_seq"),
    )
    op.create_index(
        "ix_timeline_events_birth_occurred",
        "timeline_events",
        ["birth_id", "occurred_at"],
    )

    op.create_table(
        "media_assets",
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
            "uploaded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", media_kind, nullable=False),
        sa.Column("original_s3_key", sa.Text(), nullable=False),
        sa.Column("hot_s3_key", sa.Text(), nullable=True),
        sa.Column("cold_s3_key", sa.Text(), nullable=True),
        sa.Column(
            "storage_tier", media_storage_tier, nullable=False, server_default="hot"
        ),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column(
            "is_visible_to_viewers",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "auth_challenges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("identifier_kind", auth_identifier_kind, nullable=False),
        sa.Column("salt", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("magic_link_token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_auth_challenges_identifier", "auth_challenges", ["identifier"])


def downgrade() -> None:
    op.drop_index("ix_auth_challenges_identifier", table_name="auth_challenges")
    op.drop_table("auth_challenges")
    op.drop_table("media_assets")
    op.drop_index("ix_timeline_events_birth_occurred", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_table("births")
    op.drop_table("family_memberships")
    op.drop_table("families")
    op.drop_index("ix_users_phone_unique", table_name="users")
    op.drop_index("ix_users_email_unique", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_name in (
        "auth_identifier_kind",
        "media_storage_tier",
        "media_kind",
        "audience_scope",
        "timeline_event_type",
        "birth_storage_tier",
        "birth_status",
        "family_role",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
