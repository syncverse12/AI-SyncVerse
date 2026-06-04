"""Initial schema — projects, risk_reports, alerts, metrics_snapshots, incidents

Revision ID: 0001_initial
Revises: 
Create Date: 2025-05-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), default="planning"),
        sa.Column("start_date", sa.DateTime(timezone=True)),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.Column("budget_usd", sa.Float, nullable=False),
        sa.Column("estimated_hours", sa.Float, nullable=False),
        sa.Column("meta", postgresql.JSON, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "risk_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_type", sa.String(50)),
        sa.Column("overall_risk_score", sa.Float),
        sa.Column("severity", sa.String(20)),
        sa.Column("delay_probability", sa.Float),
        sa.Column("budget_overrun_probability", sa.Float),
        sa.Column("delivery_confidence", sa.Float),
        sa.Column("burnout_probability", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("report_json", postgresql.JSON),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_risk_reports_project_id", "risk_reports", ["project_id"])
    op.create_index("ix_risk_reports_generated_at", "risk_reports", ["generated_at"])

    op.create_table(
        "risk_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("severity", sa.String(20)),
        sa.Column("risk_category", sa.String(50)),
        sa.Column("status", sa.String(30), default="active"),
        sa.Column("title", sa.String(500)),
        sa.Column("message", sa.Text),
        sa.Column("root_cause", sa.Text),
        sa.Column("ai_insight", sa.Text),
        sa.Column("recommended_action", sa.Text),
        sa.Column("previous_risk_score", sa.Float),
        sa.Column("current_risk_score", sa.Float),
        sa.Column("delta", sa.Float),
        sa.Column("escalation_level", sa.Integer, default=1),
        sa.Column("notify_roles", postgresql.JSON, default=[]),
        sa.Column("acknowledged_by", sa.String(255), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fired_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_project_id", "risk_alerts", ["project_id"])
    op.create_index("ix_alerts_severity", "risk_alerts", ["severity"])
    op.create_index("ix_alerts_status", "risk_alerts", ["status"])

    op.create_table(
        "metrics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("overall_risk_score", sa.Float),
        sa.Column("metrics_json", postgresql.JSON),
    )
    op.create_index("ix_snapshots_project_id", "metrics_snapshots", ["project_id"])
    op.create_index("ix_snapshots_snapshot_at", "metrics_snapshots", ["snapshot_at"])

    op.create_table(
        "historical_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_type", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("root_cause", sa.Text),
        sa.Column("impact", sa.Text),
        sa.Column("resolution", sa.Text),
        sa.Column("duration_hours", sa.Float, nullable=True),
        sa.Column("was_preventable", sa.Boolean, default=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("vector_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("historical_incidents")
    op.drop_table("metrics_snapshots")
    op.drop_table("risk_alerts")
    op.drop_table("risk_reports")
    op.drop_table("projects")
