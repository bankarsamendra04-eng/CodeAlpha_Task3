"""
AI Music Studio - Music Data Models and Validation Schemas (Pydantic v2)
Defines strict structured parameters interpreted from natural-language prompts
and advanced generation request/response models with user control overrides.
"""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, field_validator


class MusicMood(str, Enum):
    PEACEFUL = "peaceful"
    CALM = "calm"
    MELANCHOLIC = "melancholic"
    ENERGETIC = "energetic"
    UPLIFTING = "uplifting"
    DRAMATIC = "dramatic"
    MYSTERIOUS = "mysterious"
    ROMANTIC = "romantic"
    JOYFUL = "joyful"
    DARK = "dark"
    HOPEFUL = "hopeful"
    NEUTRAL = "neutral"


class MusicInstrument(str, Enum):
    PIANO = "piano"
    GRAND_PIANO = "grand piano"
    ELECTRIC_PIANO = "electric piano"
    HARPSICHORD = "harpsichord"
    ACOUSTIC_GUITAR = "acoustic guitar"
    ELECTRIC_GUITAR = "electric guitar"
    VIOLIN = "violin"
    CELLO = "violoncello"
    FLUTE = "flute"
    CLARINET = "clarinet"
    TRUMPET = "trumpet"
    PIPE_ORGAN = "pipe organ"
    MARIMBA = "marimba"


class LevelEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MusicalKey(str, Enum):
    C = "C"
    C_SHARP = "C#"
    D = "D"
    D_SHARP = "D#"
    E = "E"
    F = "F"
    F_SHARP = "F#"
    G = "G"
    G_SHARP = "G#"
    A = "A"
    A_SHARP = "A#"
    B = "B"


class MusicalScale(str, Enum):
    MAJOR = "major"
    MINOR = "minor"


class MusicPromptRequest(BaseModel):
    """Raw prompt sent by the user."""
    prompt: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural-language description of the desired musical composition.",
        examples=["Create a peaceful piano melody for meditation at 70 BPM."],
    )


class MusicParameters(BaseModel):
    """
    Structured musical parameters parsed from natural language.
    Validates and standardizes attributes before handing off to the LSTM generator.
    """
    mood: str = Field(
        default="peaceful",
        description="Emotional mood or aesthetic of the composition.",
    )
    instrument: str = Field(
        default="piano",
        description="Target instrument family for performance and synthesis.",
    )
    style: str = Field(
        default="classical",
        description="Musical style, genre, or intended context (e.g., meditation, romantic, ambient).",
    )
    tempo: float = Field(
        default=100.0,
        ge=40.0,
        le=240.0,
        description="Playback tempo in Beats Per Minute (BPM), restricted between 40 and 240.",
    )
    complexity: LevelEnum = Field(
        default=LevelEnum.MEDIUM,
        description="Harmonic/rhythmic density (low, medium, high).",
    )
    energy: LevelEnum = Field(
        default=LevelEnum.MEDIUM,
        description="Energy and dynamic level (low, medium, high).",
    )
    duration_seconds: int = Field(
        default=60,
        ge=10,
        le=600,
        description="Estimated duration of generated piece in seconds (10 to 600).",
    )
    key: Optional[str] = Field(
        default="C",
        description="Musical key tonic note (e.g., C, D, G, A, F#).",
    )
    scale: Optional[str] = Field(
        default="major",
        description="Musical scale mode (major or minor).",
    )

    @field_validator("tempo", mode="before")
    @classmethod
    def sanitize_tempo(cls, v: Any) -> float:
        """Clamp tempo to safe, musical boundaries (40-240 BPM)."""
        try:
            val = float(v)
            if val < 40.0:
                return 40.0
            if val > 240.0:
                return 240.0
            return round(val, 1)
        except (ValueError, TypeError):
            return 100.0

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def sanitize_duration(cls, v: Any) -> int:
        """Clamp duration between 10s and 600s (10 minutes max)."""
        try:
            val = int(v)
            if val < 10:
                return 10
            if val > 600:
                return 600
            return val
        except (ValueError, TypeError):
            return 60

    @field_validator("instrument", mode="before")
    @classmethod
    def sanitize_instrument(cls, v: Any) -> str:
        """Standardize instrument name to lowercase string."""
        if not v or not isinstance(v, str):
            return "piano"
        clean = v.strip().lower()
        if "guitar" in clean:
            return "acoustic guitar" if "acoustic" in clean else "electric guitar" if "electric" in clean else "acoustic guitar"
        if "piano" in clean:
            return "electric piano" if "electric" in clean else "piano"
        if "organ" in clean:
            return "pipe organ"
        if "cello" in clean:
            return "violoncello"
        return clean

    @field_validator("mood", "style", mode="before")
    @classmethod
    def sanitize_strings(cls, v: Any) -> str:
        """Ensure safe, clean alphanumeric string values."""
        if not v or not isinstance(v, str):
            return "peaceful"
        cleaned = "".join(c for c in v if c.isalnum() or c in (" ", "-", "_")).strip().lower()
        return cleaned or "peaceful"

    @field_validator("key", mode="before")
    @classmethod
    def sanitize_key(cls, v: Any) -> str:
        """Standardize key tonic (e.g. C, G#, Bb)."""
        if not v or not isinstance(v, str):
            return "C"
        clean = v.strip().upper()
        # Handle flats/sharps
        if len(clean) > 1 and clean[1] == "B":
            clean = clean[0] + "b"
        valid_roots = ["C", "C#", "DB", "D", "D#", "EB", "E", "F", "F#", "GB", "G", "G#", "AB", "A", "A#", "BB", "B"]
        if clean.upper() in valid_roots:
            return clean.capitalize() if "b" in clean else clean
        return "C"

    @field_validator("scale", mode="before")
    @classmethod
    def sanitize_scale(cls, v: Any) -> str:
        """Standardize scale mode (major or minor)."""
        if not v or not isinstance(v, str):
            return "major"
        clean = v.strip().lower()
        return "minor" if "min" in clean else "major"


class MusicPromptResponse(BaseModel):
    """Response returned after Groq interprets the prompt."""
    success: bool = True
    prompt: str
    parameters: MusicParameters
    suggested_temperature: float = Field(
        default=0.8,
        ge=0.1,
        le=2.0,
        description="Calculated sampling temperature for the LSTM generator based on complexity/energy.",
    )
    suggested_num_events: int = Field(
        default=64,
        ge=16,
        le=512,
        description="Suggested number of sequential events for the LSTM to predict.",
    )
    fallback_used: bool = False
    message: Optional[str] = None


class MusicGenerateRequest(BaseModel):
    """
    Request payload for full music generation pipeline.
    Supports either pure natural-language, pure advanced controls, or hybrid merged inputs.
    """
    prompt: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional natural-language music prompt to interpret and compose.",
        examples=["Create a peaceful piano melody for meditation"],
    )

    # Optional explicit user control overrides (Priority over Groq suggestions)
    mood: Optional[str] = Field(
        default=None,
        description="Explicit user mood override (e.g., peaceful, melancholic, energetic).",
    )
    instrument: Optional[str] = Field(
        default=None,
        description="Explicit user instrument override (e.g., piano, violin, acoustic guitar).",
    )
    tempo: Optional[float] = Field(
        default=None,
        ge=40.0,
        le=240.0,
        description="Explicit user tempo override in BPM (40-240).",
    )
    duration_seconds: Optional[int] = Field(
        default=None,
        ge=10,
        le=600,
        description="Explicit user duration override in seconds (10-600).",
    )
    complexity: Optional[LevelEnum] = Field(
        default=None,
        description="Explicit user complexity override (low, medium, high).",
    )
    key: Optional[str] = Field(
        default=None,
        description="Explicit musical key tonic override (e.g., C, D, G, A).",
    )
    scale: Optional[str] = Field(
        default=None,
        description="Explicit musical scale mode override (major or minor).",
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=2.0,
        description="Explicit creativity / temperature sampling override (0.1 to 2.0).",
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Explicit random seed for deterministic reproducibility.",
    )

    # Rendering & execution options
    render_audio: bool = Field(
        default=True,
        description="Whether to attempt automatic synthesis of playable audio (WAV) via FluidSynth.",
    )
    num_events_override: Optional[int] = Field(
        default=None,
        ge=16,
        le=512,
        description="Optional manual override for number of predicted musical events.",
    )

    @field_validator("prompt", mode="before")
    @classmethod
    def sanitize_prompt(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        clean = str(v).strip()
        return clean if clean else None

    @field_validator("tempo", mode="before")
    @classmethod
    def sanitize_override_tempo(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        try:
            val = float(v)
            return max(40.0, min(240.0, round(val, 1)))
        except (ValueError, TypeError):
            return None

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def sanitize_override_duration(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            val = int(v)
            return max(10, min(600, val))
        except (ValueError, TypeError):
            return None

    @field_validator("temperature", mode="before")
    @classmethod
    def sanitize_override_temperature(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        try:
            val = float(v)
            return max(0.1, min(2.0, round(val, 2)))
        except (ValueError, TypeError):
            return None

    @field_validator("random_seed", mode="before")
    @classmethod
    def sanitize_override_seed(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class FileReference(BaseModel):
    """Safe, client-facing file reference without revealing private filesystem paths."""
    filename: str
    download_url: str
    file_type: str  # 'midi' or 'audio'
    size_bytes: int


class GenerationMetadata(BaseModel):
    """Detailed musical & structural metadata for the generated piece."""
    prompt: Optional[str]
    interpreted_parameters: MusicParameters
    user_overrides_applied: Dict[str, Any]
    prompt_parser: str
    temperature_used: float
    num_events_generated: int
    duration_quarter_lengths: float
    notes_count: int
    chords_count: int
    rests_count: int
    tempo_bpm: float
    instrument: str
    key: Optional[str] = "C"
    scale: Optional[str] = "major"
    ai_disclosure: str = (
        "AI-Generated Music Disclosure: This musical composition was composed algorithmically "
        "using an artificial intelligence neural network (LSTM) trained on symbolic MIDI data from "
        "the MAESTRO dataset. Outputs are not automatically guaranteed to be copyright-free. Users "
        "bear sole responsibility for rights clearance prior to commercial release or broadcast. "
        "See docs/RESPONSIBLE_AI.md."
    )


class MusicGenerateResponse(BaseModel):
    """Complete client-facing generation response."""
    success: bool = True
    generation_id: str
    metadata: GenerationMetadata
    midi_file: FileReference
    audio_file: Optional[FileReference] = None
    audio_status: str  # 'rendered', 'renderer_unavailable', or 'skipped'
    ai_disclosure: str = (
        "AI-Generated Music Disclosure: Generated algorithmically by an artificial intelligence "
        "model. Not performed by human musicians. Users retain full responsibility for rights "
        "clearance prior to commercial distribution. See docs/RESPONSIBLE_AI.md."
    )
    message: str

class GenerationDetailResponse(BaseModel):
    """Full detail of a saved generation record from the database."""
    id: str
    generation_id: str
    prompt: Optional[str] = None
    prompt_parser: str
    interpreted_parameters: Dict[str, Any]
    user_overrides: Optional[Dict[str, Any]] = None
    model_version: str
    tempo_bpm: float
    instrument: str
    musical_key: Optional[str] = "C"
    scale: Optional[str] = "major"
    temperature: float
    random_seed: Optional[int] = None
    num_events_generated: int
    duration_quarter_lengths: float
    generation_status: str
    generation_duration_ms: int
    error_info: Optional[str] = None
    midi_file: Optional[FileReference] = None
    audio_file: Optional[FileReference] = None
    audio_status: str
    created_at: datetime


class GenerationHistoryListResponse(BaseModel):
    """Paginated list of generation records."""
    total: int
    page: int
    limit: int
    items: List[GenerationDetailResponse]