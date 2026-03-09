"""
SQLAlchemy ORM schema for Vocence database.

Defines the database schema using SQLAlchemy 2.0 declarative style.

Centralized Service Architecture Models:
- RegisteredMiner: Centrally validated miners (synced from metagraph)
- ValidatorEvaluation: Evaluations submitted by validators
- PerformanceMetrics: Per-validator metrics (calculated server-side from evaluations)
- BlockedEntity: Blocked entities
- ValidatorRegistry: Registered validators
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    Index,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)
from sqlalchemy.sql import func


class BaseModel(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class RegisteredMiner(BaseModel):
    """Centrally validated miners.
    
    Stores miner validation state synced from metagraph with HuggingFace
    and Chutes endpoint verification.
    """
    __tablename__ = "registered_miners"
    
    uid: Mapped[int] = mapped_column(Integer, primary_key=True)
    miner_hotkey: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    block: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Model info (from commitment)
    model_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_revision: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Chutes info
    chute_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chute_slug: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Validation state
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    invalid_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    __table_args__ = (
        Index("idx_registered_miners_is_valid", "is_valid"),
        Index("idx_registered_miners_hotkey", "miner_hotkey"),
    )
    
    def __repr__(self) -> str:
        return f"<RegisteredMiner(uid={self.uid}, hotkey='{self.miner_hotkey[:8]}...', is_valid={self.is_valid})>"


class ValidatorEvaluation(BaseModel):
    """Evaluation submitted by a validator.
    
    Stores evaluation results from validators. Metrics are calculated
    from this table by the metrics aggregation task.
    """
    __tablename__ = "validator_evaluations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    validator_hotkey: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    miner_hotkey: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Evaluation info
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_prefix: Mapped[str] = mapped_column(String(512), nullable=False)
    
    # Evaluation result
    wins: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pre-signed audio URLs (validator sends; used by dashboard for playback)
    original_audio_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_audio_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    __table_args__ = (
        Index("idx_validator_evaluations_validator", "validator_hotkey"),
        Index("idx_validator_evaluations_miner", "miner_hotkey"),
        Index("idx_validator_evaluations_eval", "evaluation_id"),
        Index("idx_validator_evaluations_date", "evaluated_at"),
        Index("idx_validator_evaluations_unique", "validator_hotkey", "evaluation_id", "miner_hotkey", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<ValidatorEvaluation(validator='{self.validator_hotkey[:8]}...', eval='{self.evaluation_id}', wins={self.wins})>"


class PerformanceMetrics(BaseModel):
    """Per-validator metrics for dashboard (calculated from submitted evaluations).
    
    Stores metrics calculated server-side from ValidatorEvaluation data.
    Each validator's metrics for each miner are stored separately.
    Only valid miners are included (invalid miner metrics are removed).
    
    Note: These metrics are for dashboard/monitoring purposes only.
    Validators calculate their own metrics from their own S3 buckets
    for weight setting.
    """
    __tablename__ = "performance_metrics"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    miner_hotkey: Mapped[str] = mapped_column(String(64), nullable=False)
    validator_hotkey: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Metrics data (calculated from validator_evaluations)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    total_evaluations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    __table_args__ = (
        Index("idx_performance_miner", "miner_hotkey"),
        Index("idx_performance_validator", "validator_hotkey"),
        Index("idx_performance_miner_validator", "miner_hotkey", "validator_hotkey", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<PerformanceMetrics(miner='{self.miner_hotkey[:8]}...', validator='{self.validator_hotkey[:8]}...', win_rate={self.win_rate:.2%})>"


class BlockedEntity(BaseModel):
    """Blocked miner hotkeys.
    
    Centralized blacklist managed by subnet admins.
    """
    __tablename__ = "blocked_entities"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hotkey: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    added_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # admin hotkey
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<BlockedEntity(hotkey='{self.hotkey[:8]}...')>"


class ValidatorRegistry(BaseModel):
    """Registered validators.
    
    Tracks validators that submit evaluations to the service.
    """
    __tablename__ = "validator_registry"
    
    uid: Mapped[int] = mapped_column(Integer, primary_key=True)
    hotkey: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    stake: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    # Optional S3 bucket for validator's samples
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Activity tracking
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<ValidatorRegistry(uid={self.uid}, hotkey='{self.hotkey[:8]}...', stake={self.stake})>"


class LiveEvaluationPending(BaseModel):
    """Live evaluation "started" notice for dashboard status bar.

    Validators POST to /evaluations/live after generating the prompt (before/during
    miner evaluation). When POST /evaluations (batch) is received for the same
    (validator_hotkey, evaluation_id), the row is removed so the bar shows win/lose.
    """
    __tablename__ = "live_evaluation_pending"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    validator_hotkey: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_summary: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    miner_hotkeys: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of hotkeys
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_live_eval_pending_validator", "validator_hotkey"),
        Index("idx_live_eval_pending_eval", "evaluation_id"),
        Index("idx_live_eval_pending_unique", "validator_hotkey", "evaluation_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<LiveEvaluationPending(validator='{self.validator_hotkey[:8]}...', eval='{self.evaluation_id}')>"

