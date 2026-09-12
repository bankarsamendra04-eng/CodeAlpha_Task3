"""
AI Music Studio - SaaS Usage Tracking & Limit Enforcement Service
Provides centralized business limit validation, database-backed usage tracking,
and quota reporting across:
- Generations count (monthly billing cycle)
- Generation duration (seconds per composition)
- Audio rendering capabilities (WAV / SoundFont)
- Storage consumption (bytes & MB)
- Programmatic API requests
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.config.plans import PlanTier, PlanDefinition, get_plan_definition, PLAN_REGISTRY
from backend.database.models import User, UserUsage, UsageMetric

logger = logging.getLogger("ai_music_studio.usage_service")


class UsageService:
    """Manages SaaS tier checks, quota validation, and database usage ledger."""

    @staticmethod
    def get_user_plan(user: Optional[User]) -> PlanDefinition:
        """Resolve the active PlanDefinition for the given user, defaulting to FREE."""
        if user is None:
            return get_plan_definition("FREE")
        
        tier = getattr(user, "subscription_tier", "FREE") or "FREE"
        # Admin users inherit ENTERPRISE capabilities by default unless an explicit tier is configured
        if getattr(user, "role", "USER") == "ADMIN" and tier == "FREE":
            return get_plan_definition("ENTERPRISE")
        return get_plan_definition(tier)

    @staticmethod
    def get_or_create_usage(user_id: str, db: Session) -> UserUsage:
        """Retrieve or initialize the UserUsage record for the current monthly billing cycle."""
        now = datetime.now(timezone.utc)
        year = now.year
        month = now.month

        usage = (
            db.query(UserUsage)
            .filter(
                UserUsage.user_id == user_id,
                UserUsage.billing_cycle_year == year,
                UserUsage.billing_cycle_month == month,
            )
            .first()
        )

        if not usage:
            usage = UserUsage(
                user_id=user_id,
                billing_cycle_year=year,
                billing_cycle_month=month,
                generations_count=0,
                total_duration_seconds=0.0,
                audio_renders_count=0,
                storage_bytes_used=0,
                api_calls_count=0,
            )
            db.add(usage)
            db.commit()
            db.refresh(usage)

        return usage

    def validate_generation_request(
        self,
        user: Optional[User],
        requested_duration: int,
        render_audio: bool,
        is_api: bool = False,
        has_advanced_controls: bool = False,
        db: Optional[Session] = None,
        enforce_hard_limits: bool = True,
    ) -> Dict[str, Any]:
        """
        Validate whether the user's current subscription plan allows the generation request.
        Raises HTTPException(403) with clear upgrade guidance if any limit is exceeded.
        """
        plan = self.get_user_plan(user)
        limits = plan.limits

        # 1. Check Duration Limit
        effective_duration = requested_duration if requested_duration is not None else 60
        if effective_duration > limits.max_duration_seconds:
            if enforce_hard_limits:
                logger.warning(
                    "User %s requested duration (%ds) exceeds plan limit (%ds)",
                    user.username if user else "guest",
                    effective_duration,
                    limits.max_duration_seconds,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Requested duration ({effective_duration}s) exceeds the maximum allowed "
                        f"for the {plan.name} plan ({limits.max_duration_seconds}s). "
                        f"Please upgrade to Creator or Pro to unlock longer compositions."
                    ),
                )

        # 2. Check Audio Rendering Permission
        if render_audio and not limits.can_render_audio:
            if enforce_hard_limits:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"WAV audio rendering is not enabled on the {plan.name} plan. "
                        f"Upgrade to Creator or Pro to synthesize high-quality audio files."
                    ),
                )

        # 3. Check API Access Permission
        if is_api and not limits.api_access_allowed:
            if enforce_hard_limits:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Direct API access is not permitted under the {plan.name} plan. "
                        f"Upgrade to Pro, Education, or Enterprise to generate an API key."
                    ),
                )

        # 4. Check Monthly Generation Quota (for authenticated users with active DB session)
        usage_info = {
            "tier": plan.tier.value,
            "plan_name": plan.name,
            "generations_used": 0,
            "generations_limit": limits.max_generations_per_month,
            "remaining_generations": limits.max_generations_per_month if limits.max_generations_per_month != -1 else -1,
        }

        if user and db:
            usage = self.get_or_create_usage(user.id, db)
            usage_info["generations_used"] = usage.generations_count

            if limits.max_generations_per_month != -1:
                remaining = max(0, limits.max_generations_per_month - usage.generations_count)
                usage_info["remaining_generations"] = remaining

                if usage.generations_count >= limits.max_generations_per_month and enforce_hard_limits:
                    logger.warning(
                        "User %s exceeded monthly generation limit (%d/%d)",
                        user.username,
                        usage.generations_count,
                        limits.max_generations_per_month,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Monthly generation quota reached ({usage.generations_count}/{limits.max_generations_per_month}) "
                            f"for the {plan.name} plan. Please upgrade your subscription to continue generating music."
                        ),
                    )

            # 5. Check Storage Quota
            max_storage_bytes = limits.max_storage_mb * 1024 * 1024
            if usage.storage_bytes_used >= max_storage_bytes and enforce_hard_limits:
                storage_mb = usage.storage_bytes_used / (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Storage quota reached ({storage_mb:.1f} MB / {limits.max_storage_mb} MB) "
                        f"for the {plan.name} plan. Please delete previous tracks or upgrade to increase your quota."
                    ),
                )

        return usage_info

    def record_usage(
        self,
        user: Optional[User],
        duration_sec: float,
        audio_rendered: bool,
        storage_bytes: int = 0,
        is_api: bool = False,
        db: Optional[Session] = None,
    ) -> Optional[UserUsage]:
        """Record resource usage metrics in the database for the billing cycle."""
        if not user or not db:
            return None

        try:
            usage = self.get_or_create_usage(user.id, db)
            usage.generations_count += 1
            usage.total_duration_seconds += round(float(duration_sec), 2)
            if audio_rendered:
                usage.audio_renders_count += 1
            if storage_bytes > 0:
                usage.storage_bytes_used += storage_bytes
            if is_api:
                usage.api_calls_count += 1
            
            db.commit()
            db.refresh(usage)
            return usage
        except Exception as exc:
            db.rollback()
            logger.error("Failed to record user usage in database: %s", exc)
            return None

    def get_user_usage_summary(self, user: User, db: Session) -> Dict[str, Any]:
        """Compile an exhaustive SaaS quota and consumption summary for the client."""
        plan = self.get_user_plan(user)
        limits = plan.limits
        usage = self.get_or_create_usage(user.id, db)

        generations_limit = limits.max_generations_per_month
        remaining_gen = (
            max(0, generations_limit - usage.generations_count)
            if generations_limit != -1
            else -1
        )

        storage_mb_used = round(usage.storage_bytes_used / (1024 * 1024), 2)
        storage_percent = (
            round((storage_mb_used / limits.max_storage_mb) * 100, 1)
            if limits.max_storage_mb > 0
            else 0.0
        )

        return {
            "tier": plan.tier.value,
            "plan_name": plan.name,
            "monthly_price_usd": plan.monthly_price_usd,
            "billing_cycle": {
                "year": usage.billing_cycle_year,
                "month": usage.billing_cycle_month,
            },
            "generations": {
                "used": usage.generations_count,
                "limit": generations_limit,
                "remaining": remaining_gen,
                "unlimited": generations_limit == -1,
            },
            "duration": {
                "total_seconds": usage.total_duration_seconds,
                "max_per_generation": limits.max_duration_seconds,
            },
            "audio_renders": {
                "used": usage.audio_renders_count,
                "allowed": limits.can_render_audio,
                "can_download": limits.can_download_audio,
            },
            "storage": {
                "used_mb": storage_mb_used,
                "limit_mb": limits.max_storage_mb,
                "percent_used": min(100.0, storage_percent),
            },
            "api": {
                "calls_used": usage.api_calls_count,
                "limit_per_day": limits.max_api_calls_per_day,
                "allowed": limits.api_access_allowed,
            },
            "features": {
                "advanced_controls": limits.advanced_controls_allowed,
                "project_management": limits.project_management_allowed,
                "generation_history": limits.generation_history_allowed,
                "research_features": limits.research_features,
                "classroom_accounts": limits.classroom_accounts,
                "custom_models": limits.custom_models,
            },
        }


# Global service singleton instance
_usage_service = UsageService()


def get_usage_service() -> UsageService:
    return _usage_service
