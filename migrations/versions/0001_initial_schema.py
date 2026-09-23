"""0001 Initial Schema for Private Messenger

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-22 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "is_online",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_index("idx_users_id", "users", ["id"])
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index(
        "idx_users_username_lower",
        "users",
        [sa.text("lower(username)")],
        unique=False,
    )

    # 2. Chats Table
    chat_type_enum = postgresql.ENUM(
        "direct",
        "group",
        name="chat_type_enum",
        create_type=False,
    )
    chat_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "chat_type",
            chat_type_enum,
            nullable=False,
            server_default="direct",
        ),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_chats_id", "chats", ["id"])

    # 3. Group Profiles Table
    op.create_table(
        "group_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
    )

    # 4. Chat Members Table
    member_role_enum = postgresql.ENUM(
        "owner",
        "member",
        name="member_role_enum",
        create_type=False,
    )
    member_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "chat_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            member_role_enum,
            nullable=False,
            server_default="member",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_read_message_id", sa.Integer(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chat_id",
            "user_id",
            name="uq_chat_member",
        ),
    )

    op.create_index(
        "idx_chat_members_chat_user",
        "chat_members",
        ["chat_id", "user_id"],
    )

    # 5. Messages Table
    message_type_enum = postgresql.ENUM(
        "text",
        "image",
        "video",
        "file",
        "voice",
        name="message_type_enum",
        create_type=False,
    )
    message_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column(
            "message_type",
            message_type_enum,
            nullable=False,
            server_default="text",
        ),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(length=1024), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("reply_to_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_id"],
            ["messages.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_messages_id", "messages", ["id"])
    op.create_index(
        "idx_messages_chat_created",
        "messages",
        ["chat_id", "created_at"],
    )
    op.create_index(
        "idx_messages_sender_created",
        "messages",
        ["sender_id", "created_at"],
    )

    # 6. Calls Table
    call_type_enum = postgresql.ENUM(
        "audio",
        "video",
        name="call_type_enum",
        create_type=False,
    )
    call_type_enum.create(op.get_bind(), checkfirst=True)

    call_status_enum = postgresql.ENUM(
        "initiated",
        "ringing",
        "accepted",
        "rejected",
        "ended",
        "missed",
        "busy",
        name="call_status_enum",
        create_type=False,
    )
    call_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("caller_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=True),
        sa.Column(
            "call_type",
            call_type_enum,
            nullable=False,
            server_default="audio",
        ),
        sa.Column(
            "status",
            call_status_enum,
            nullable=False,
            server_default="initiated",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["caller_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["receiver_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_calls_caller_receiver",
        "calls",
        ["caller_id", "receiver_id"],
    )
    op.create_index(
        "idx_calls_started_at",
        "calls",
        ["started_at"],
    )

    # 7. Device Tokens Table
    device_platform_enum = postgresql.ENUM(
        "android",
        "ios",
        "web",
        name="device_platform_enum",
        create_type=False,
    )
    device_platform_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_token", sa.String(length=512), nullable=False),
        sa.Column(
            "platform",
            device_platform_enum,
            nullable=False,
            server_default="android",
        ),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "device_token",
            name="uq_user_device_token",
        ),
    )

    op.create_index(
        "idx_device_tokens_user",
        "device_tokens",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("device_tokens")
    op.drop_table("calls")
    op.drop_table("messages")
    op.drop_table("chat_members")
    op.drop_table("group_profiles")
    op.drop_table("chats")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS device_platform_enum")
    op.execute("DROP TYPE IF EXISTS call_status_enum")
    op.execute("DROP TYPE IF EXISTS call_type_enum")
    op.execute("DROP TYPE IF EXISTS message_type_enum")
    op.execute("DROP TYPE IF EXISTS member_role_enum")
    op.execute("DROP TYPE IF EXISTS chat_type_enum")
