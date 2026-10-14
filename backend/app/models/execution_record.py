"""Durable audit entries for approvals and each execution step attempt."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from app.database import Base


class ExecutionRecord(Base):
    __tablename__ = "execution_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("task_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    attempt = Column(Integer, nullable=False, default=1)
    event_type = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    verified = Column(Boolean, nullable=False, default=False)
    verification_result = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
