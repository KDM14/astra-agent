"""SQLAlchemy declarative models for persistent task storage."""

from __future__ import annotations

import datetime
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TaskRecord(Base):
    """Database record for a task."""
    __tablename__ = "tasks"

    task_id = Column(String(64), primary_key=True, index=True)
    objective = Column(Text, nullable=False)
    state = Column(String(32), nullable=False, default="PENDING")
    plan_json = Column(Text, nullable=True)
    parameters_json = Column(Text, nullable=True)
    workspace_dir = Column(String(512), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    steps = relationship("StepRecord", back_populates="task", cascade="all, delete-orphan")
    checkpoints = relationship("CheckpointRecord", back_populates="task", cascade="all, delete-orphan")


class StepRecord(Base):
    """Database record for an executed plan step."""
    __tablename__ = "task_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    order = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    tool_name = Column(String(128), nullable=False)
    arguments_json = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING")
    output_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Float, default=0.0)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    task = relationship("TaskRecord", back_populates="steps")


class CheckpointRecord(Base):
    """Database record for execution checkpoints."""
    __tablename__ = "task_checkpoints"

    checkpoint_id = Column(String(64), primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("tasks.task_id"), nullable=False, index=True)
    state = Column(String(32), nullable=False)
    step_index = Column(Integer, nullable=False)
    plan_snapshot_json = Column(Text, nullable=False)
    memory_snapshot_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    task = relationship("TaskRecord", back_populates="checkpoints")


class AuditRecord(Base):
    """Database record for security and audit events."""
    __tablename__ = "audit_events"

    event_id = Column(String(64), primary_key=True, index=True)
    task_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    actor = Column(String(64), nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
