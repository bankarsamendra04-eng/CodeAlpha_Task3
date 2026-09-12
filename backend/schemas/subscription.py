"""
AI Music Studio - SaaS Subscription & Plan Schemas
Defines request and response models for plans, quotas, and subscription updates.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.config.plans import PlanTier, PlanLimits, PlanDefinition


class PlanListResponse(BaseModel):
    """Response containing all available subscription plans."""
    total_plans: int
    plans: List[PlanDefinition]


class SubscriptionTierUpdateRequest(BaseModel):
    """Request model for upgrading or switching subscription tiers."""
    tier: PlanTier = Field(
        ...,
        description="Target subscription tier (FREE, CREATOR, PRO, EDUCATION, ENTERPRISE).",
        examples=["CREATOR"],
    )


class SubscriptionTierUpdateResponse(BaseModel):
    """Response returned upon successful subscription update."""
    success: bool
    user_id: str
    username: str
    previous_tier: str
    current_tier: str
    message: str
