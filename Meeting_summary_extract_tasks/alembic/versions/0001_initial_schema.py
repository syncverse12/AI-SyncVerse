"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("role", sa.String(80), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "meetings",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("host_id", postgresql.UUID(), nullable=False),
        sa.Column("status", sa.String(20), server_default="PENDING"),
        sa.Column("language", sa.String(10), server_default="en"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["host_id"], ["employees.id"]),
    )

    op.create_table(
        "meeting_attendees",
        sa.Column("meeting_id", postgresql.UUID(), nullable=False),
        sa.Column("employee_id", postgresql.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("meeting_id", "employee_id"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(), nullable=False),
        sa.Column("full_text_en", sa.Text(), server_default=""),
        sa.Column("full_text_ar", sa.Text(), server_default=""),
        sa.Column("utterances", postgresql.JSONB(), server_default="[]"),
        sa.Column("word_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(), nullable=False),
        sa.Column("assignee_id", postgresql.UUID(), nullable=True),
        sa.Column("assignee_raw", sa.String(150), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), server_default="MEDIUM"),
        sa.Column("status", sa.String(20), server_default="TODO"),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("estimated_hours", sa.Float(), nullable=True),
        sa.Column("category", sa.String(80), server_default="general"),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["employees.id"]),
    )

    op.create_table(
        "meeting_summaries",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(), nullable=False),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("key_points", postgresql.JSONB(), server_default="[]"),
        sa.Column("decisions", postgresql.JSONB(), server_default="[]"),
        sa.Column("blockers", postgresql.JSONB(), server_default="[]"),
        sa.Column("next_steps", postgresql.JSONB(), server_default="[]"),
        sa.Column("action_items", postgresql.JSONB(), server_default="[]"),
        sa.Column("full_markdown", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_tasks_assignee_id", "tasks", ["assignee_id"])
    op.create_index("ix_tasks_meeting_id", "tasks", ["meeting_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_meetings_host_id", "meetings", ["host_id"])
    op.create_index("ix_meetings_status", "meetings", ["status"])


def downgrade():
    op.drop_table("meeting_summaries")
    op.drop_table("tasks")
    op.drop_table("transcripts")
    op.drop_table("meeting_attendees")
    op.drop_table("meetings")
    op.drop_table("employees")
