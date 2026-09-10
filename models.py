"""SQLAlchemy models for BAT3 validation database."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src_new.config.loader import DATABASE_URL

Base = declarative_base()


class MddbEntry(Base):
    """MDDB entries table - tracks entries from MDDBR."""

    __tablename__ = "mddb_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    local_accession = Column(String(50), unique=True, nullable=False, index=True)
    project_name = Column(String(255), nullable=True)
    status = Column(String(50), default="pending", index=True)  # pending, processing, completed, failed
    is_complete = Column(Boolean, default=False, index=True)  # tracks if metadata is fully fetched
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    runs = relationship("Bat3Run", back_populates="entry", cascade="all, delete-orphan")
    queue_items = relationship("ValidationQueue", back_populates="entry", cascade="all, delete-orphan")
    results = relationship("ValidationResult", back_populates="entry", cascade="all, delete-orphan")
    ground_truth_signatures = relationship("GroundTruthSignature", back_populates="entry", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_mddb_entries_status", "status"),
    )


class Bat3Run(Base):
    """BAT3 runs table - tracks individual validation runs."""

    __tablename__ = "bat3_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("mddb_entries.id"), nullable=False)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    celery_task_id = Column(String(100), nullable=True, index=True)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    input_dir = Column(String(500), nullable=True)
    results_path = Column(String(500), nullable=True)
    config_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    entry = relationship("MddbEntry", back_populates="runs")

    __table_args__ = (
        Index("idx_bat3_runs_status", "status"),
        Index("idx_bat3_runs_entry_id", "entry_id"),
    )


class ValidationQueue(Base):
    """Validation queue table - tracks queued validation requests."""

    __tablename__ = "validation_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("mddb_entries.id"), nullable=False)
    batch_id = Column(String(100), nullable=True, index=True)
    run_id = Column(Integer, ForeignKey("bat3_runs.id"), nullable=True, index=True)
    priority = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    status = Column(String(50), default="queued")  # queued, processing, completed, failed
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    entry = relationship("MddbEntry", back_populates="queue_items")

    __table_args__ = (
        Index("idx_validation_queue_status", "status"),
        Index("idx_validation_queue_priority", "priority", "created_at"),
    )


class ValidationResult(Base):
    """Validation results table - stores validation outcomes."""

    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("mddb_entries.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("bat3_runs.id"), nullable=True)
    result_type = Column(String(100), nullable=True)  # e.g., 'structure_validation', 'data_quality'
    status = Column(String(50), default="pending")  # pending, passed, failed, warning
    details = Column(Text, nullable=True)  # JSON string with detailed results
    metrics = Column(Text, nullable=True)  # JSON string with metrics
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    entry = relationship("MddbEntry", back_populates="results")

    __table_args__ = (
        Index("idx_validation_results_entry_id", "entry_id"),
        Index("idx_validation_results_status", "status"),
    )


class MddbProject(Base):
    """MDDB projects table - tracks projects from MDDBR."""

    __tablename__ = "mddb_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    local_accession = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_mddb_projects_status", "status"),
    )


class MddbReference(Base):
    """MDDB references table - tracks references for projects."""

    __tablename__ = "mddb_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("mddb_projects.id"), nullable=False)
    ref_type = Column(String(50), nullable=True)  # e.g., 'publication', 'database'
    ref_url = Column(String(500), nullable=True)
    ref_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_mddb_references_project_id", "project_id"),
    )


class MddbFilenote(Base):
    """MDDB filenotes table - tracks file metadata."""

    __tablename__ = "mddb_filenotes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("mddb_projects.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    file_url = Column(String(500), nullable=True)
    checksum = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_mddb_filenotes_project_id", "project_id"),
    )


class BatchRun(Base):
    """Batch runs table - tracks batch validation operations."""

    __tablename__ = "batch_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(100), unique=True, nullable=False, index=True)
    total_entries = Column(Integer, default=0)
    completed_entries = Column(Integer, default=0)
    failed_entries = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_batch_runs_status", "status"),
    )


class AuditLog(Base):
    """Audit log table - tracks API operations."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False)  # e.g., 'entry_created', 'run_started'
    resource_type = Column(String(50), nullable=True)  # e.g., 'entry', 'run'
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_created_at", "created_at"),
    )


class IndexingJob(Base):
    """Indexing jobs table - tracks MDDBR indexing operations."""

    __tablename__ = "indexing_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    job_type = Column(String(50), nullable=False)  # mddbr_index, fetch_missing, ground_truth_fetch
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_indexing_jobs_status", "status"),
        Index("idx_indexing_jobs_job_type", "job_type"),
    )


class GroundTruthSignature(Base):
    """Ground truth signatures table - stores external reference signatures."""

    __tablename__ = "ground_truth_signatures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("mddb_entries.id"), nullable=False)
    signature_type = Column(String(50), nullable=False)  # uniprot, pdb, inchi, pubchem
    signature_value = Column(Text, nullable=False)  # the actual signature/identifier
    source_url = Column(String(500), nullable=True)
    raw_data = Column(Text, nullable=True)  # JSON string with full response
    fetched_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    entry = relationship("MddbEntry", back_populates="ground_truth_signatures")

    __table_args__ = (
        Index("idx_ground_truth_signatures_entry_id", "entry_id"),
        Index("idx_ground_truth_signatures_type", "signature_type"),
    )


# Database session factory
engine = create_engine(DATABASE_URL, pool_size=30, max_overflow=20, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


class IndexingActivityLog(Base):
    """Indexing activity log - real-time streaming of indexing operations."""

    __tablename__ = "indexing_activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), nullable=False, index=True)  # References IndexingJob.job_id
    activity_type = Column(String(50), nullable=False)  # project_fetched, refs_added, filenotes_added, error, progress
    message = Column(Text, nullable=False)
    severity = Column(String(20), default="info")  # info, success, warning, error
    details = Column(JSON, nullable=True)  # Additional structured data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_activity_log_job_id", "job_id"),
        Index("idx_activity_log_created_at", "created_at"),
        Index("idx_activity_log_type", "activity_type"),
    )
