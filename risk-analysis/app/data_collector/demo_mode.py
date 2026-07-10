"""
Demo Mode — returns realistic sample data instead of calling any backend.
Activated by setting DEMO_MODE=true in .env. Lets the whole pipeline
(Metrics Engine -> Risk Engine -> LLM -> Report Builder) be exercised
end-to-end before the real backend integration is wired up.

This is NOT a test mock (see tests/mocks/mock_backend.py for that) — this
runs inside the actual deployed service so a human can hit
POST /projects/demo-1/analyze and see a real report.
"""

from datetime import datetime, timedelta, timezone
from app.data_collector.base import DataCollector
from app.schemas.context_schema import (
    ProjectContext, ProjectInfo, TaskItem, TimelineItem, MilestoneItem,
    ConfirmedRiskItem, TimeLogItem, TeamMemberItem, MeetingItem,
)

NOW = lambda: datetime.now(timezone.utc)


class DemoModeCollector(DataCollector):
    async def collect(self, project_id: str) -> ProjectContext:
        now = NOW()

        return ProjectContext(
            project=ProjectInfo(
                project_id=project_id,
                project_name="AI-SyncVerse Demo Project",
                budget=50000,
                priority="High",
                status="active",
                created_at=now - timedelta(days=60),
            ),
            tasks=[
                TaskItem(task_id="t1", title="Design DB schema", status="done",
                         priority="High", created_at=now - timedelta(days=55), assigned_user_id="u1"),
                TaskItem(task_id="t2", title="Build auth service", status="done",
                         priority="High", created_at=now - timedelta(days=45), assigned_user_id="u1"),
                TaskItem(task_id="t3", title="Risk microservice API", status="in_progress",
                         priority="Critical", created_at=now - timedelta(days=20), assigned_user_id="u2"),
                TaskItem(task_id="t4", title="Frontend dashboard", status="in_progress",
                         priority="High", created_at=now - timedelta(days=15), assigned_user_id="u2"),
                TaskItem(task_id="t5", title="Integration testing", status="todo",
                         priority="Medium", created_at=now - timedelta(days=5), assigned_user_id="u2",
                         depends_on_task_ids=["t3", "t4"]),
                TaskItem(task_id="t6", title="Deployment to HF Spaces", status="todo",
                         priority="Medium", created_at=now - timedelta(days=3), assigned_user_id="u1",
                         depends_on_task_ids=["t5"]),
            ],
            timeline=[
                TimelineItem(timeline_id="tl1", start_date=now - timedelta(days=60),
                             due_date=now + timedelta(days=10), estimated_time=480, status="active"),
            ],
            milestones=[
                MilestoneItem(milestone_id="m1", name="Backend integration ready",
                               target_date=now - timedelta(days=2), status="pending"),  # overdue
                MilestoneItem(milestone_id="m2", name="Final defense demo ready",
                               target_date=now + timedelta(days=10), status="pending"),
            ],
            confirmed_risks=[
                ConfirmedRiskItem(risk_id="r1", risk_name="Backend endpoints not finalized",
                                   severity="high", status="open", date_identified=now - timedelta(days=3)),
            ],
            time_logs=[
                TimeLogItem(time_id="tlg1", task_id="t3", user_id="u2",
                             start_time=now - timedelta(days=2, hours=4), end_time=now - timedelta(days=2),
                             duration_minutes=240),
                TimeLogItem(time_id="tlg2", task_id="t4", user_id="u2",
                             start_time=now - timedelta(days=1, hours=6), end_time=now - timedelta(days=1),
                             duration_minutes=360),
            ],
            team_members=[
                TeamMemberItem(user_id="u1", task_capacity=3, assigned_task_count=2),
                TeamMemberItem(user_id="u2", task_capacity=2, assigned_task_count=3),  # overloaded
            ],
            meetings=[
                MeetingItem(meeting_id="mt1", start_time=now - timedelta(days=6)),
            ],
            collection_mode="demo",
            missing_sources=[],
            data_completeness=1.0,
        )
