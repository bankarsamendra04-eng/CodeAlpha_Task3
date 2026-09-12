"""
AI Music Studio - SQLAlchemy Database Models
Defines PostgreSQL-ready relational models for users, projects, generations,
files, feedback, and usage metrics.

Models:
- User
- Project
- Generation
- GeneratedFile
- Feedback
- UsageMetric

Security:
- Never stores API keys, raw secrets, or private credentials.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.database.connection import Base


def generate_uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    """Represents a studio user/creator."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid_str)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(16), default="USER", nullable=False)  # 'USER' or 'ADMIN'
    subscription_tier = Column(String(32), default="FREE", nullable=False, index=True)  # FREE, CREATOR, PRO, EDUCATION, ENTERPRISE
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    generations = relationship("Generation", back_populates="user", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")
    usage_records = relationship("UserUsage", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    """Represents a creative workspace or album collection belonging to a user."""
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(128), nullable=False, default="Untitled Music Project")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="projects")
    generations = relationship("Generation", back_populates="project", cascade="all, delete-orphan")


class Generation(Base):
    """
    Core record for every AI music composition generated.
    Stores prompt, parameters, model version, timestamps, duration, and file references.
    """
    __tablename__ = "generations"

    id = Column(String(36), primary_key=True, default=generate_uuid_str, index=True)
    generation_id = Column(String(64), unique=True, index=True, nullable=False)  # e.g., 'gen_5a01d43ee3e4'
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)

    # Prompt & Parameters
    prompt = Column(Text, nullable=True)
    prompt_parser = Column(String(32), default="fallback_heuristics")  # 'groq_llm', 'fallback_heuristics', 'manual'
    interpreted_parameters = Column(JSON, nullable=False, default=dict)
    user_overrides = Column(JSON, nullable=True, default=dict)

    # Model & Music Metadata
    model_version = Column(String(32), default="lstm_v1", nullable=False)
    tempo_bpm = Column(Float, nullable=False, default=120.0)
    instrument = Column(String(64), nullable=False, default="piano")
    musical_key = Column(String(8), default="C")
    scale = Column(String(16), default="major")
    temperature = Column(Float, default=0.85)
    random_seed = Column(Integer, nullable=True)
    num_events_generated = Column(Integer, default=0)
    duration_quarter_lengths = Column(Float, default=0.0)

    # Execution Timing & Status
    generation_status = Column(String(32), default="completed", index=True)  # 'completed', 'failed', 'processing'
    generation_duration_ms = Column(Integer, default=0)  # Time taken in milliseconds
    error_info = Column(Text, nullable=True)

    # File References (client-accessible URLs/slugs, never internal machine paths)
    midi_file_name = Column(String(256), nullable=True)
    midi_file_url = Column(String(512), nullable=True)
    midi_size_bytes = Column(Integer, default=0)

    audio_status = Column(String(32), default="skipped")  # 'rendered', 'renderer_unavailable', 'skipped', 'failed'
    audio_file_name = Column(String(256), nullable=True)
    audio_file_url = Column(String(512), nullable=True)
    audio_size_bytes = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="generations")
    project = relationship("Project", back_populates="generations")
    files = relationship("GeneratedFile", back_populates="generation", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="generation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_generations_created_at_desc", created_at.desc()),
        Index("ix_generations_user_created_at", user_id, created_at.desc()),
        Index("ix_generations_status_created", generation_status, created_at.desc()),
    )


class GeneratedFile(Base):
    """Explicit asset ledger for all generated media files (MIDI, WAV, MP3, etc.)."""
    __tablename__ = "generated_files"

    id = Column(String(36), primary_key=True, default=generate_uuid_str)
    generation_id = Column(String(36), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    file_type = Column(String(16), nullable=False)  # 'midi', 'audio_wav', 'audio_mp3'
    filename = Column(String(256), nullable=False)
    download_url = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    mime_type = Column(String(64), default="application/octet-stream")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship
    generation = relationship("Generation", back_populates="files")


class Feedback(Base):
    """User rating, sentiment, and feedback on generated compositions."""
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid_str)
    generation_id = Column(String(36), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating = Column(Integer, nullable=True)  # 1 to 5 stars
    is_liked = Column(Boolean, nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    generation = relationship("Generation", back_populates="feedback")
    user = relationship("User", back_populates="feedback")

    __table_args__ = (
        Index("ix_feedback_user_created", user_id, created_at.desc()),
    )


class UsageMetric(Base):
    """Aggregated usage and telemetry metric log for studio observability."""
    __tablename__ = "usage_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid_str)
    event_type = Column(String(64), nullable=False, index=True)  # 'generation_completed', 'download_midi', 'download_audio'
    client_ip_hash = Column(String(64), nullable=True)  # Anonymized IP hash
    generation_duration_ms = Column(Integer, default=0)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True, nullable=False)

    __table_args__ = (
        Index("ix_usage_metrics_event_created", event_type, created_at.desc()),
    )


class UserUsage(Base):
    """
    Tracks monthly billing-cycle resource usage per user for SaaS limit enforcement.
    Tracks:
    - Generations count
    - Cumulative duration seconds
    - Audio renders count
    - Storage bytes used
    - API requests count
    """
    __tablename__ = "user_usages"

    id = Column(String(36), primary_key=True, default=generate_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    billing_cycle_year = Column(Integer, nullable=False)
    billing_cycle_month = Column(Integer, nullable=False)

    generations_count = Column(Integer, default=0, nullable=False)
    total_duration_seconds = Column(Float, default=0.0, nullable=False)
    audio_renders_count = Column(Integer, default=0, nullable=False)
    storage_bytes_used = Column(Integer, default=0, nullable=False)
    api_calls_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="usage_records")

    __table_args__ = (
        UniqueConstraint("user_id", "billing_cycle_year", "billing_cycle_month", name="uq_user_billing_cycle"),
        Index("ix_user_usage_user_cycle", user_id, billing_cycle_year, billing_cycle_month),
    )