import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Enum as SAEnum, Table, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from AI_services.app.database.session import Base
import enum


def gen_uuid():
    return str(uuid.uuid4())


# ── Enums ────────────────────────────────────────────────────────────────────

class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class MeetingStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ── Association table: meeting ↔ employee (attendees) ─────────────────────

meeting_attendees = Table(
    "meeting_attendees",
    Base.metadata,
    Column("meeting_id", UUID, ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True),
    Column("employee_id", UUID, ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
)


# ── Models ────────────────────────────────────────────────────────────────────

class Employee(Base):
    __tablename__ = "employees"

    id = Column(UUID, primary_key=True, default=gen_uuid)
    name = Column(String(120), nullable=False)
    email = Column(String(200), nullable=False, unique=True)
    hashed_password = Column(String(200), nullable=False)
    department = Column(String(100), nullable=True)
    role = Column(String(80), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meetings = relationship("Meeting", secondary=meeting_attendees, back_populates="attendees")
    tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assignee_id")

    def __repr__(self):
        return f"<Employee {self.name}>"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID, primary_key=True, default=gen_uuid)
    title = Column(String(255), nullable=False)
    host_id = Column(UUID, ForeignKey("employees.id"), nullable=False)
    status = Column(SAEnum(MeetingStatus), default=MeetingStatus.PENDING)
    language = Column(String(10), default="en")
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    host = relationship("Employee", foreign_keys=[host_id])
    attendees = relationship("Employee", secondary=meeting_attendees, back_populates="meetings")
    transcript = relationship("Transcript", back_populates="meeting", uselist=False)
    tasks = relationship("Task", back_populates="meeting")
    summary = relationship("MeetingSummary", back_populates="meeting", uselist=False)

    def __repr__(self):
        return f"<Meeting {self.title}>"


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(UUID, primary_key=True, default=gen_uuid)
    meeting_id = Column(UUID, ForeignKey("meetings.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_text_en = Column(Text, default="")
    full_text_ar = Column(Text, default="")
    utterances = Column(JSONB, default=list)
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="transcript")

    def __repr__(self):
        return f"<Transcript meeting={self.meeting_id}>"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID, primary_key=True, default=gen_uuid)
    meeting_id = Column(UUID, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    assignee_id = Column(UUID, ForeignKey("employees.id"), nullable=True)
    assignee_raw = Column(String(150), nullable=True)

    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(SAEnum(TaskPriority), default=TaskPriority.MEDIUM)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.TODO)
    deadline = Column(DateTime, nullable=True)
    estimated_hours = Column(Float, nullable=True)
    category = Column(String(80), default="general")
    source_quote = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="tasks")
    assignee = relationship("Employee", back_populates="tasks", foreign_keys=[assignee_id])

    def __repr__(self):
        return f"<Task {self.title[:40]}>"


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    id = Column(UUID, primary_key=True, default=gen_uuid)
    meeting_id = Column(UUID, ForeignKey("meetings.id", ondelete="CASCADE"), unique=True, nullable=False)

    overview = Column(Text, nullable=False)
    key_points = Column(JSONB, default=list)
    decisions = Column(JSONB, default=list)
    blockers = Column(JSONB, default=list)
    next_steps = Column(JSONB, default=list)
    action_items = Column(JSONB, default=list)
    full_markdown = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    meeting = relationship("Meeting", back_populates="summary")

    def __repr__(self):
        return f"<Summary meeting={self.meeting_id}>"
