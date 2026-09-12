"""
AI Music Studio - Admin Dashboard Schemas (Pydantic v2)
Structured models for administrative metrics, dataset status, system errors, and feedback.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DatasetStatusInfo(BaseModel):
    name: str = "MAESTRO v3.0.0 (MIDI)"
    status: str = "healthy"
    total_midi_files: int = 0
    valid_files: int = 0
    total_duration_hours: float = 0.0
    total_notes: int = 0
    total_chords: int = 0
    splits: Dict[str, int] = Field(default_factory=dict)
    vocabulary_size: int = 0
    processed_cache_status: str = "ready"


class ModelVersionInfo(BaseModel):
    version: str = "lstm_v1"
    architecture: str = "2-Layer LSTM + Embedding + Dropout"
    model_file: str = "best_model.keras"
    model_size_mb: float = 0.0
    vocabulary_tokens: int = 0
    sequence_length: int = 50
    embedding_dim: int = 128
    lstm_units: int = 256
    training_status: str = "completed"
    best_loss: Optional[float] = None
    best_accuracy: Optional[float] = None


class ApiUsageSummary(BaseModel):
    total_api_calls: int = 0
    groq_llm_calls: int = 0
    fallback_heuristic_calls: int = 0
    manual_controls_calls: int = 0
    midi_downloads: int = 0
    audio_downloads: int = 0
    avg_latency_ms: float = 0.0


class GenerationStats(BaseModel):
    total: int = 0
    today: int = 0
    successful: int = 0
    failed: int = 0
    success_rate_percent: float = 100.0


class RecentGenerationAdminItem(BaseModel):
    id: str
    generation_id: str
    username: Optional[str] = "Anonymous / Public"
    prompt: Optional[str] = None
    instrument: str
    tempo_bpm: float
    musical_key: Optional[str] = "C"
    scale: Optional[str] = "major"
    temperature: float
    generation_status: str
    generation_duration_ms: int
    midi_file_name: Optional[str] = None
    audio_status: str
    created_at: datetime


class FeedbackAdminItem(BaseModel):
    id: str
    generation_id: str
    username: Optional[str] = "Anonymous"
    rating: Optional[int] = None
    is_liked: Optional[bool] = None
    comment: Optional[str] = None
    created_at: datetime


class SystemErrorAdminItem(BaseModel):
    generation_id: str
    prompt: Optional[str] = None
    error_info: str
    created_at: datetime


class DailyActivityPoint(BaseModel):
    date: str
    generations: int
    success: int
    failed: int


class InstrumentDistributionPoint(BaseModel):
    instrument: str
    count: int


class CommonFeedbackWord(BaseModel):
    word: str
    count: int


class AdminDashboardResponse(BaseModel):
    admin_user: str
    timestamp: datetime

    # 1. Total users
    total_users: int = 0

    # 2-5. Generations overview
    generations_stats: GenerationStats

    # 6. API usage
    api_usage: ApiUsageSummary

    # 7. Model version info
    model_info: ModelVersionInfo

    # 8. Dataset status
    dataset_status: DatasetStatusInfo

    # 9. Recent generations
    recent_generations: List[RecentGenerationAdminItem] = Field(default_factory=list)

    # 10. User feedback analytics & recent items
    feedback: List[FeedbackAdminItem] = Field(default_factory=list)
    avg_rating: Optional[float] = None
    total_feedback_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    common_feedback_words: List[CommonFeedbackWord] = Field(default_factory=list)

    # 11. System errors
    system_errors: List[SystemErrorAdminItem] = Field(default_factory=list)
    total_errors_recorded: int = 0

    # Basic charts / statistics series
    daily_trend: List[DailyActivityPoint] = Field(default_factory=list)
    instrument_distribution: List[InstrumentDistributionPoint] = Field(default_factory=list)
    subscription_distribution: Dict[str, int] = Field(default_factory=dict)


class FeedbackSubmitRequest(BaseModel):
    generation_id: str
    rating: Optional[int] = Field(None, ge=1, le=5)
    is_liked: Optional[bool] = None
    comment: Optional[str] = Field(None, max_length=1000)
