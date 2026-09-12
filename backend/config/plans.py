"""
AI Music Studio - Centralized SaaS Subscription Plans & Limits Configuration
Defines business logic, feature tiers, and resource limits for:
- FREE
- CREATOR
- PRO
- EDUCATION
- ENTERPRISE

Enforces that business limits are NOT hardcoded across the codebase.
Limits can be dynamically overridden via environment variables.
"""

import os
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PlanTier(str, Enum):
    FREE = "FREE"
    CREATOR = "CREATOR"
    PRO = "PRO"
    EDUCATION = "EDUCATION"
    ENTERPRISE = "ENTERPRISE"


class PlanLimits(BaseModel):
    """Resource limits and functional capabilities for a specific plan tier."""
    max_generations_per_month: int = Field(
        ...,
        description="Maximum music generations allowed per monthly billing cycle (-1 for unlimited)."
    )
    max_duration_seconds: int = Field(
        ...,
        description="Maximum length of generated composition in seconds."
    )
    can_render_audio: bool = Field(
        ...,
        description="Whether high-fidelity WAV audio synthesis is allowed."
    )
    can_download_midi: bool = Field(
        True,
        description="Whether Standard MIDI File (SMF Type 1) download is enabled."
    )
    can_download_audio: bool = Field(
        ...,
        description="Whether rendered audio file download is enabled."
    )
    advanced_controls_allowed: bool = Field(
        ...,
        description="Whether explicit tempo, key, scale, temperature, and mood overrides are enabled."
    )
    project_management_allowed: bool = Field(
        ...,
        description="Whether user can organize generations into albums / multi-track projects."
    )
    generation_history_allowed: bool = Field(
        ...,
        description="Whether persistent history retrieval across sessions is available."
    )
    api_access_allowed: bool = Field(
        ...,
        description="Whether programmatic REST API token access is permitted."
    )
    max_storage_mb: int = Field(
        ...,
        description="Maximum persistent media storage quota in megabytes."
    )
    max_api_calls_per_day: int = Field(
        ...,
        description="Maximum API requests permitted per 24-hour rolling window (-1 for unlimited)."
    )
    research_features: bool = Field(
        False,
        description="Enables token inspection, raw logits analysis, and dataset diagnostic export."
    )
    classroom_accounts: bool = Field(
        False,
        description="Enables multi-seat student management and grading sub-accounts."
    )
    custom_models: bool = Field(
        False,
        description="Allows fine-tuning or loading private domain checkpoint weights."
    )
    dedicated_deployment: bool = Field(
        False,
        description="Private cloud or on-premise dedicated inference worker support."
    )


class PlanDefinition(BaseModel):
    """Complete product plan metadata including marketing description and limits."""
    tier: PlanTier
    name: str
    tagline: str
    description: str
    monthly_price_usd: Optional[float] = None
    is_popular: bool = False
    highlights: List[str] = Field(default_factory=list)
    limits: PlanLimits


def _get_env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


def _get_env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is not None:
        return val.lower() in ("true", "1", "yes")
    return default


# Centralized, configurable dictionary of plans.
# Limits can be adjusted in .env without touching application code.
PLAN_REGISTRY: Dict[PlanTier, PlanDefinition] = {
    PlanTier.FREE: PlanDefinition(
        tier=PlanTier.FREE,
        name="Free",
        tagline="Explore AI Composition",
        description="Perfect for hobbyists, students, and casual musicians exploring AI music generation.",
        monthly_price_usd=0.0,
        is_popular=False,
        highlights=[
            f"{_get_env_int('PLAN_FREE_MAX_GEN', 15)} generations per month",
            f"Up to {_get_env_int('PLAN_FREE_MAX_DURATION', 60)} seconds per generation",
            "Direct Standard MIDI (.mid) downloads",
            "Basic natural language prompt understanding",
            f"{_get_env_int('PLAN_FREE_MAX_STORAGE_MB', 50)} MB storage",
        ],
        limits=PlanLimits(
            max_generations_per_month=_get_env_int("PLAN_FREE_MAX_GEN", 15),
            max_duration_seconds=_get_env_int("PLAN_FREE_MAX_DURATION", 60),
            can_render_audio=_get_env_bool("PLAN_FREE_CAN_RENDER_AUDIO", True),
            can_download_midi=True,
            can_download_audio=_get_env_bool("PLAN_FREE_CAN_DOWNLOAD_AUDIO", False),
            advanced_controls_allowed=_get_env_bool("PLAN_FREE_ADVANCED_CONTROLS", False),
            project_management_allowed=False,
            generation_history_allowed=False,
            api_access_allowed=False,
            max_storage_mb=_get_env_int("PLAN_FREE_MAX_STORAGE_MB", 50),
            max_api_calls_per_day=0,
            research_features=False,
            classroom_accounts=False,
            custom_models=False,
            dedicated_deployment=False,
        ),
    ),
    PlanTier.CREATOR: PlanDefinition(
        tier=PlanTier.CREATOR,
        name="Creator",
        tagline="For Independent Artists & Producers",
        description="Ideal for songwriters, YouTubers, streamers, and indie podcast producers.",
        monthly_price_usd=19.0,
        is_popular=True,
        highlights=[
            f"{_get_env_int('PLAN_CREATOR_MAX_GEN', 200)} generations per month",
            f"Up to {_get_env_int('PLAN_CREATOR_MAX_DURATION', 90)} seconds per generation",
            "Studio-quality WAV audio downloads & synthesis",
            "Full Advanced Controls (BPM, key, scale, mood overrides)",
            "Commercial royalty-free usage rights",
            f"{_get_env_int('PLAN_CREATOR_MAX_STORAGE_MB', 1000)} MB storage",
        ],
        limits=PlanLimits(
            max_generations_per_month=_get_env_int("PLAN_CREATOR_MAX_GEN", 200),
            max_duration_seconds=_get_env_int("PLAN_CREATOR_MAX_DURATION", 90),
            can_render_audio=True,
            can_download_midi=True,
            can_download_audio=True,
            advanced_controls_allowed=True,
            project_management_allowed=False,
            generation_history_allowed=True,
            api_access_allowed=False,
            max_storage_mb=_get_env_int("PLAN_CREATOR_MAX_STORAGE_MB", 1000),
            max_api_calls_per_day=0,
            research_features=False,
            classroom_accounts=False,
            custom_models=False,
            dedicated_deployment=False,
        ),
    ),
    PlanTier.PRO: PlanDefinition(
        tier=PlanTier.PRO,
        name="Pro",
        tagline="For Professional Game & Film Composers",
        description="Built for studio musicians, game audio directors, and scoring teams requiring deeper control.",
        monthly_price_usd=49.0,
        is_popular=False,
        highlights=[
            f"{_get_env_int('PLAN_PRO_MAX_GEN', 1000)} generations per month",
            f"Up to {_get_env_int('PLAN_PRO_MAX_DURATION', 240)} seconds (4 minutes)",
            "Multi-track project management & albums",
            "Persistent full generation history & cloud syncing",
            "Developer REST API access (1,000 calls/day)",
            f"{_get_env_int('PLAN_PRO_MAX_STORAGE_MB', 10000)} MB (10 GB) storage",
        ],
        limits=PlanLimits(
            max_generations_per_month=_get_env_int("PLAN_PRO_MAX_GEN", 1000),
            max_duration_seconds=_get_env_int("PLAN_PRO_MAX_DURATION", 240),
            can_render_audio=True,
            can_download_midi=True,
            can_download_audio=True,
            advanced_controls_allowed=True,
            project_management_allowed=True,
            generation_history_allowed=True,
            api_access_allowed=True,
            max_storage_mb=_get_env_int("PLAN_PRO_MAX_STORAGE_MB", 10000),
            max_api_calls_per_day=_get_env_int("PLAN_PRO_MAX_API_CALLS", 1000),
            research_features=False,
            classroom_accounts=False,
            custom_models=False,
            dedicated_deployment=False,
        ),
    ),
    PlanTier.EDUCATION: PlanDefinition(
        tier=PlanTier.EDUCATION,
        name="Education",
        tagline="For Music Schools, Universities & Labs",
        description="Empower classrooms, music theory courses, and computational musicology research.",
        monthly_price_usd=15.0,
        is_popular=False,
        highlights=[
            f"{_get_env_int('PLAN_EDU_MAX_GEN', 500)} generations per seat",
            f"Up to {_get_env_int('PLAN_EDU_MAX_DURATION', 120)} seconds per composition",
            "Music theory analysis & token probability inspection",
            "Student accounts & shared classroom assignments",
            "Research dataset diagnostic exports",
            f"{_get_env_int('PLAN_EDU_MAX_STORAGE_MB', 5000)} MB storage",
        ],
        limits=PlanLimits(
            max_generations_per_month=_get_env_int("PLAN_EDU_MAX_GEN", 500),
            max_duration_seconds=_get_env_int("PLAN_EDU_MAX_DURATION", 120),
            can_render_audio=True,
            can_download_midi=True,
            can_download_audio=True,
            advanced_controls_allowed=True,
            project_management_allowed=True,
            generation_history_allowed=True,
            api_access_allowed=True,
            max_storage_mb=_get_env_int("PLAN_EDU_MAX_STORAGE_MB", 5000),
            max_api_calls_per_day=_get_env_int("PLAN_EDU_MAX_API_CALLS", 500),
            research_features=True,
            classroom_accounts=True,
            custom_models=False,
            dedicated_deployment=False,
        ),
    ),
    PlanTier.ENTERPRISE: PlanDefinition(
        tier=PlanTier.ENTERPRISE,
        name="Enterprise",
        tagline="Custom Infrastructure & Unlimited Scale",
        description="For media streaming platforms, AAA gaming studios, and global creative agencies.",
        monthly_price_usd=None,  # Custom quote
        is_popular=False,
        highlights=[
            "Unlimited monthly generations",
            f"Extended generation lengths (up to {_get_env_int('PLAN_ENT_MAX_DURATION', 600)}s)",
            "Private cloud or on-premise dedicated deployment",
            "Custom-tuned LSTM / Transformer model weights",
            "High-throughput programmatic API (Unlimited)",
            "Dedicated account manager & 99.9% uptime SLA",
        ],
        limits=PlanLimits(
            max_generations_per_month=-1,  # Unlimited
            max_duration_seconds=_get_env_int("PLAN_ENT_MAX_DURATION", 600),
            can_render_audio=True,
            can_download_midi=True,
            can_download_audio=True,
            advanced_controls_allowed=True,
            project_management_allowed=True,
            generation_history_allowed=True,
            api_access_allowed=True,
            max_storage_mb=_get_env_int("PLAN_ENT_MAX_STORAGE_MB", 100000),
            max_api_calls_per_day=-1,  # Unlimited
            research_features=True,
            classroom_accounts=True,
            custom_models=True,
            dedicated_deployment=True,
        ),
    ),
}


def get_plan_definition(tier: str) -> PlanDefinition:
    """Retrieve the PlanDefinition for a given tier name string, defaulting to FREE."""
    try:
        normalized_tier = PlanTier(tier.upper())
        return PLAN_REGISTRY[normalized_tier]
    except (ValueError, KeyError, AttributeError):
        return PLAN_REGISTRY[PlanTier.FREE]


def get_all_plans() -> List[PlanDefinition]:
    """Retrieve all available subscription plans in standard progression order."""
    return [
        PLAN_REGISTRY[PlanTier.FREE],
        PLAN_REGISTRY[PlanTier.CREATOR],
        PLAN_REGISTRY[PlanTier.PRO],
        PLAN_REGISTRY[PlanTier.EDUCATION],
        PLAN_REGISTRY[PlanTier.ENTERPRISE],
    ]
