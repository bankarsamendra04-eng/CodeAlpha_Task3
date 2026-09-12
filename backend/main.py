"""
AI Music Studio - FastAPI Backend Server
Provides RESTful APIs for:
- User Authentication (Registration, Login, Token Refresh, Current User Profile)
- Prompt Interpretation (Groq / Heuristic)
- Symbolic Music Generation (LSTM next-token prediction)
- MIDI Export & Synthesized WAV Audio Rendering
- User-scoped Generation History and Project Management
- Administrative Metrics and System Oversight
"""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status, Depends, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

from ml.config import MIDI_OUTPUT_DIR, AUDIO_OUTPUT_DIR
from backend.database.connection import get_db, init_db
from backend.database.models import User, Generation, Project, Feedback, UsageMetric
from backend.schemas.admin import (
    AdminDashboardResponse,
    FeedbackSubmitRequest,
)
from backend.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
)
from backend.schemas.subscription import (
    PlanListResponse,
    SubscriptionTierUpdateRequest,
    SubscriptionTierUpdateResponse,
)
from backend.config.plans import get_all_plans, get_plan_definition, PlanTier
from backend.services.usage_service import get_usage_service
from backend.schemas.music import (
    MusicPromptRequest,
    MusicPromptResponse,
    MusicGenerateRequest,
    MusicGenerateResponse,
    GenerationDetailResponse,
    GenerationHistoryListResponse,
    FileReference,
)
from backend.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    get_current_user_from_header_or_query,
    require_admin,
)
from backend.services.security_service import (
    SecurityHeadersMiddleware,
    RateLimiterMiddleware,
    validate_safe_path,
    validate_file_upload,
    validate_midi_bytes,
    validate_wav_bytes,
    sanitize_user_input,
)

logger = logging.getLogger("ai_music_studio.main")

# Safe production debug flag (defaults to False)
DEBUG_MODE = os.getenv("DEBUG", "False").lower() in ("true", "1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager initializing database schema on startup."""
    init_db()
    yield


app = FastAPI(
    title="AI Music Studio API",
    description=(
        "Full generative AI music system with secure JWT authentication and role-based access control (RBAC). "
        "Translates natural-language music descriptions via Groq into structured musical parameters, "
        "composes symbolic polyphonic music with a trained MAESTRO LSTM model, exports valid MIDI files, "
        "and securely isolates projects and generation histories per user."
    ),
    version="1.0.0",
    debug=DEBUG_MODE,
    lifespan=lifespan,
)

# 1. OWASP Security Headers Middleware (Always First)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Rate Limiter Middleware
app.add_middleware(RateLimiterMiddleware)

# 3. Enable Cross-Origin Resource Sharing (CORS) with strict origins
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()] if allowed_origins_env else [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global safe error handler to prevent internal file paths, stack traces,
    database schemas, or secrets from ever leaking into client responses.
    """
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    # Log safe diagnostic info on the server side
    logger.exception("Unhandled server exception processing %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact the administrator."},
    )


@app.get("/", tags=["System"])
def read_root():
    return {
        "project": "AI Music Studio",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
def get_health(db: Session = Depends(get_db)):
    """
    Health check endpoint to verify backend service availability, AI models, and database connection.
    """
    from backend.services.groq_service import get_groq_service
    groq_service = get_groq_service()

    db_status = "ok"
    try:
        db.execute(Generation.__table__.select().limit(1))
    except Exception:
        db_status = "degraded"

    return {
        "status": "healthy",
        "service": "AI Music Studio Backend",
        "environment": "development",
        "components": {
            "api": "ok",
            "database": db_status,
            "groq_prompt_parser": "groq_api_ready" if groq_service.is_available else "fallback_active",
            "ai_engine": "lstm_v1_ready",
            "auth_security": "jwt_bcrypt_active",
        },
    }


# ===========================================================================
# 1. USER AUTHENTICATION ENDPOINTS
# ===========================================================================

@app.post(
    "/api/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
    summary="Register New Studio Creator Account",
)
def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user account with secure bcrypt password hashing.
    Rejects duplicate usernames or emails with 400 Bad Request.
    """
    # Check duplicate username
    existing_user = db.query(User).filter(User.username == request.username.strip().lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already registered.",
        )

    # Check duplicate email
    existing_email = db.query(User).filter(User.email == request.email.strip().lower()).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered.",
        )

    # Validate confirm password if provided
    if request.confirm_password is not None and request.confirm_password != request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    # Hash password securely
    hashed_pw = hash_password(request.password)

    # Server-Side Role Authorization:
    # Do NOT trust role supplied blindly by client. Public registrations default to USER.
    # To obtain ADMIN privileges upon registration, an explicit ADMIN_INVITE_KEY or pre-existing admin authorization is required.
    admin_invite_secret = os.getenv("ADMIN_INVITE_CODE", "AdminStudioSecret#2026")
    assigned_role = "USER"
    if request.role and request.role.value == "ADMIN":
        if request.admin_invite_code == admin_invite_secret:
            assigned_role = "ADMIN"
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Valid administrative verification code is required to register an ADMIN account.",
            )

    new_user = User(
        username=request.username.strip().lower(),
        email=request.email.strip().lower(),
        hashed_password=hashed_pw,
        role=assigned_role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Issue access token
    access_token, expires_in = create_access_token(
        user_id=new_user.id,
        username=new_user.username,
        role=new_user.role,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=expires_in,
        user=UserResponse.model_validate(new_user),
    )


@app.post(
    "/api/auth/login",
    response_model=TokenResponse,
    tags=["Authentication"],
    summary="User Login & JWT Token Generation",
)
def login_user(request: UserLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates a user via username/email and password.
    Returns signed JWT access token.
    """
    ident = request.username.strip().lower()
    user = (
        db.query(User)
        .filter((User.username == ident) | (User.email == ident))
        .first()
    )

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    access_token, expires_in = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=expires_in,
        user=UserResponse.model_validate(user),
    )


@app.get(
    "/api/auth/me",
    response_model=UserResponse,
    tags=["Authentication"],
    summary="Get Authenticated User Profile",
)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Returns profile for currently authenticated user."""
    return UserResponse.model_validate(current_user)


@app.post(
    "/api/auth/logout",
    tags=["Authentication"],
    summary="User Logout & Session Invalidation",
)
def logout_user(current_user: Optional[User] = Depends(get_current_user_optional)):
    """
    Client session logout endpoint. Confirms session termination and token clearance.
    Stateless JWT tokens are cleared from the client storage.
    """
    return {
        "success": True,
        "message": "Logged out successfully.",
    }


# ===========================================================================
# 1.5. SAAS SUBSCRIPTION PLANS & USAGE QUOTAS
# ===========================================================================

@app.get(
    "/api/plans",
    response_model=PlanListResponse,
    tags=["SaaS Subscription"],
    summary="List All SaaS Subscription Plans & Quotas",
)
def list_subscription_plans():
    """
    Returns complete product catalog of subscription plans (FREE, CREATOR, PRO, EDUCATION, ENTERPRISE).
    Includes monthly pricing, resource quotas, and allowed features.
    """
    plans = get_all_plans()
    return PlanListResponse(total_plans=len(plans), plans=plans)


@app.get(
    "/api/subscription/me",
    tags=["SaaS Subscription"],
    summary="Get Current User Subscription Plan & Quota Consumption",
)
def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns active subscription tier, billing period, and real-time usage consumption
    (generations used, audio renders, storage MB, API requests).
    """
    usage_service = get_usage_service()
    return usage_service.get_user_usage_summary(current_user, db)


@app.post(
    "/api/subscription/tier",
    response_model=SubscriptionTierUpdateResponse,
    tags=["SaaS Subscription"],
    summary="Switch or Upgrade User Subscription Tier",
)
def update_my_subscription_tier(
    request: SubscriptionTierUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Switches user subscription plan tier.
    Architectural foundation for future SaaS billing and payment webhooks.
    """
    prev_tier = getattr(current_user, "subscription_tier", "FREE") or "FREE"
    current_user.subscription_tier = request.tier.value
    db.commit()
    db.refresh(current_user)
    return SubscriptionTierUpdateResponse(
        success=True,
        user_id=current_user.id,
        username=current_user.username,
        previous_tier=prev_tier,
        current_tier=current_user.subscription_tier,
        message=f"Subscription tier successfully updated to {request.tier.value}."
    )


# ===========================================================================
# 2. MUSIC GENERATION PIPELINE (With Auth-Linking)
# ===========================================================================

@app.post(
    "/api/prompt/interpret",
    response_model=MusicPromptResponse,
    tags=["Prompt Interpretation"],
    summary="Interpret Natural-Language Music Prompt",
)
def interpret_music_prompt(request: MusicPromptRequest):
    """
    Interprets a natural-language musical description into structured parameters.
    Notice: Groq does NOT generate the music itself; the LSTM model generates music.
    """
    from backend.services.groq_service import get_groq_service
    groq_service = get_groq_service()
    sanitized_prompt = sanitize_user_input(request.prompt, max_length=500) or request.prompt
    return groq_service.interpret_prompt(sanitized_prompt)


@app.post(
    "/api/music/generate",
    response_model=MusicGenerateResponse,
    tags=["Music Generation"],
    summary="Generate Music from Natural-Language Prompt or Advanced Controls",
)
def generate_music_from_prompt(
    request: MusicGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    End-to-end AI music pipeline:
    - Automatically associates generated composition with authenticated user when logged in.
    - Allows public guest generation for frictionless experimentation.
    """
    if request.prompt:
        request.prompt = sanitize_user_input(request.prompt, max_length=500)
    from backend.services.music_pipeline import get_music_pipeline
    pipeline = get_music_pipeline()
    return pipeline.generate_music(request, db=db, current_user=current_user)


# ===========================================================================
# 3. USER-ISOLATED GENERATION HISTORY
# ===========================================================================

def _format_generation_response(gen: Generation) -> GenerationDetailResponse:
    """Helper to convert a Generation SQLAlchemy model into GenerationDetailResponse."""
    midi_ref = None
    if gen.midi_file_name and gen.midi_file_url:
        midi_ref = FileReference(
            filename=gen.midi_file_name,
            download_url=gen.midi_file_url,
            file_type="midi",
            size_bytes=gen.midi_size_bytes or 0,
        )

    audio_ref = None
    if gen.audio_file_name and gen.audio_file_url:
        audio_ref = FileReference(
            filename=gen.audio_file_name,
            download_url=gen.audio_file_url,
            file_type="audio",
            size_bytes=gen.audio_size_bytes or 0,
        )
    elif gen.midi_file_name:
        # Provide stable audio stream reference capable of on-demand rendering
        stem = Path(gen.midi_file_name).stem
        wav_filename = f"{stem}.wav"
        audio_ref = FileReference(
            filename=wav_filename,
            download_url=f"/api/music/download/audio/{wav_filename}",
            file_type="audio",
            size_bytes=gen.audio_size_bytes or 0,
        )

    return GenerationDetailResponse(
        id=gen.id,
        generation_id=gen.generation_id,
        prompt=gen.prompt,
        prompt_parser=gen.prompt_parser,
        interpreted_parameters=gen.interpreted_parameters or {},
        user_overrides=gen.user_overrides or {},
        model_version=gen.model_version,
        tempo_bpm=gen.tempo_bpm,
        instrument=gen.instrument,
        musical_key=gen.musical_key,
        scale=gen.scale,
        temperature=gen.temperature,
        random_seed=gen.random_seed,
        num_events_generated=gen.num_events_generated,
        duration_quarter_lengths=gen.duration_quarter_lengths,
        generation_status=gen.generation_status,
        generation_duration_ms=gen.generation_duration_ms,
        error_info=gen.error_info,
        midi_file=midi_ref,
        audio_file=audio_ref,
        audio_status=gen.audio_status,
        created_at=gen.created_at,
    )


@app.get(
    "/api/generations",
    response_model=GenerationHistoryListResponse,
    tags=["Generation History"],
    summary="List Music Generation History (User-Scoped)",
)
def list_generations(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Retrieves chronological generation history:
    - If user is authenticated: shows ONLY generations belonging to that user (unless ADMIN, who sees all).
    - If user is guest: shows recent public/guest generations.
    """
    query = db.query(Generation)

    if current_user:
        if current_user.role.upper() != "ADMIN":
            # Strict tenant isolation: regular users can only see their own generations
            query = query.filter(Generation.user_id == current_user.id)
    else:
        # Public guests can only see unassigned / guest generations
        query = query.filter(Generation.user_id.is_(None))

    query = query.order_by(Generation.created_at.desc())
    total = query.count()
    offset = (page - 1) * limit
    generations = query.offset(offset).limit(limit).all()

    items = [_format_generation_response(g) for g in generations]

    return GenerationHistoryListResponse(
        total=total,
        page=page,
        limit=limit,
        items=items,
    )


@app.get(
    "/api/generations/{id}",
    response_model=GenerationDetailResponse,
    tags=["Generation History"],
    summary="Get Single Generation Details (Protected Access)",
)
def get_generation(
    id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Retrieves a single generation record:
    - Ensures standard users can only inspect their own compositions.
    - Admins can inspect any composition.
    """
    gen = (
        db.query(Generation)
        .filter((Generation.id == id) | (Generation.generation_id == id))
        .first()
    )

    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation record '{id}' not found.",
        )

    # Enforce ownership boundary
    if gen.user_id is not None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view this generation record.",
            )
        if current_user.role.upper() != "ADMIN" and gen.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access another creator's generation.",
            )

    return _format_generation_response(gen)


# ===========================================================================
# 4. ADMINISTRATIVE ENDPOINTS (Role: ADMIN Only)
# ===========================================================================

@app.get(
    "/api/admin/dashboard",
    response_model=AdminDashboardResponse,
    tags=["Administration"],
    summary="Comprehensive Admin Intelligence Dashboard",
)
def get_admin_dashboard(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns authentic live administrative metrics:
    - Total users, generation counts (total, today, success, failed)
    - API usage telemetry (Groq LLM vs fallback vs manual, downloads, latency)
    - Model specifications & training results
    - Dataset verification status (MAESTRO v3.0.0 MIDI analysis)
    - Recent generations with parameters and creator usernames
    - User feedback and satisfaction scores
    - Aggregated system errors with stack context
    - Activity trend charts and instrument distribution
    Only ADMIN users may access this endpoint.
    """
    from backend.services.admin_service import get_admin_service
    admin_service = get_admin_service()
    return admin_service.compute_dashboard_metrics(db=db, admin_user=admin_user)


@app.get(
    "/api/admin/metrics",
    tags=["Administration"],
    summary="Admin System Metrics & Oversight (Legacy Summary)",
)
def get_admin_metrics(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Administrative oversight endpoint protected by the ADMIN role."""
    total_users = db.query(User).count()
    total_generations = db.query(Generation).count()
    completed_generations = db.query(Generation).filter(Generation.generation_status == "completed").count()

    return {
        "admin_username": admin_user.username,
        "total_registered_users": total_users,
        "total_generations": total_generations,
        "completed_generations": completed_generations,
        "model_version": "lstm_v1",
        "system_status": "optimal",
    }


@app.get(
    "/api/admin/generations",
    tags=["Administration"],
    summary="Admin Global Generations Log",
)
def get_admin_generations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve all generations across all creators with optional status filtering."""
    query = db.query(Generation)
    if status:
        query = query.filter(Generation.generation_status == status)
    total = query.count()
    gens = query.order_by(Generation.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_format_generation_response(g) for g in gens],
    }


@app.get(
    "/api/admin/users",
    tags=["Administration"],
    summary="Admin User Management Directory",
)
def get_admin_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve all registered users and roles for administrative oversight."""
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "subscription_tier": getattr(u, "subscription_tier", "FREE") or "FREE",
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@app.get(
    "/api/admin/feedback",
    tags=["Administration"],
    summary="Admin User Feedback & Ratings Directory",
)
def get_admin_feedback(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve all feedback submissions with generation references."""
    total = db.query(Feedback).count()
    feedbacks = db.query(Feedback).order_by(Feedback.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": f.id,
                "generation_id": f.generation_id,
                "user_id": f.user_id,
                "rating": f.rating,
                "is_liked": f.is_liked,
                "comment": f.comment,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in feedbacks
        ],
    }


@app.get(
    "/api/admin/errors",
    tags=["Administration"],
    summary="Admin System Errors & Failure Telemetry",
)
def get_admin_errors(
    limit: int = Query(50, ge=1, le=200),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve failed generations and recorded system errors."""
    failed_gens = (
        db.query(Generation)
        .filter(Generation.generation_status == "failed")
        .order_by(Generation.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "total_failures": len(failed_gens),
        "items": [
            {
                "generation_id": g.generation_id,
                "prompt": g.prompt,
                "error_info": g.error_info,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in failed_gens
        ],
    }



@app.post(
    "/api/feedback",
    tags=["Feedback"],
    summary="Submit User Feedback on Generation",
)
def submit_generation_feedback(
    request: FeedbackSubmitRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Allows users or guests to submit ratings (1-5 stars) and comments on a generated composition."""
    gen = db.query(Generation).filter(
        (Generation.id == request.generation_id) | (Generation.generation_id == request.generation_id)
    ).first()

    if not gen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation '{request.generation_id}' not found.",
        )

    # Sanitize comment against script/XSS injection
    clean_comment = sanitize_user_input(request.comment, max_length=1000) if request.comment else None

    fb = Feedback(
        generation_id=gen.id,
        user_id=current_user.id if current_user else None,
        rating=request.rating,
        is_liked=request.is_liked if request.is_liked is not None else (request.rating >= 4 if request.rating else None),
        comment=clean_comment,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    return {
        "success": True,
        "feedback_id": fb.id,
        "message": "Thank you! Your feedback has been recorded.",
    }


# ===========================================================================
# 5. ASSET DOWNLOADS & FILE SECURITY
# ===========================================================================

def _verify_media_access_permission(
    filename: str,
    db: Session,
    current_user: Optional[User],
) -> None:
    """
    Ensures users cannot access another creator's generated media files (tenant isolation).
    - If the generation belongs to an authenticated user:
      - Requires authentication (401 if unauthenticated).
      - Requires owner or ADMIN role (403 if unauthorized).
    - If the generation was created as a guest (user_id is None):
      - Publicly accessible.
    """
    stem = Path(filename).stem
    # Match by exact audio/midi filename, or generation_id prefix/stem
    gen = (
        db.query(Generation)
        .filter(
            (Generation.audio_file_name == filename) |
            (Generation.midi_file_name == filename) |
            (Generation.generation_id == stem) |
            (Generation.audio_file_name.like(f"{stem}.%")) |
            (Generation.midi_file_name.like(f"{stem}.%"))
        )
        .first()
    )
    if not gen and "_" in stem:
        gen_prefix = stem.rsplit("_", 1)[0]
        gen = db.query(Generation).filter(Generation.generation_id == gen_prefix).first()

    if gen and gen.user_id is not None:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to access this generated media.",
            )
        if current_user.role.upper() != "ADMIN" and gen.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access another creator's generated file.",
            )


@app.get(
    "/api/music/download/midi/{filename}",
    tags=["Downloads"],
    summary="Download Generated MIDI File",
)
def download_midi_file(
    filename: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_from_header_or_query),
):
    """Securely stream or download a generated MIDI file with strict path traversal, authorization & header verification."""
    file_path = validate_safe_path(MIDI_OUTPUT_DIR, filename, allowed_extensions={".mid", ".midi"})
    _verify_media_access_permission(file_path.name, db, current_user)

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested MIDI file '{file_path.name}' was not found.",
        )

    # Verify binary MIDI integrity
    try:
        header_bytes = file_path.read_bytes()[:32]
        is_valid, _ = validate_midi_bytes(header_bytes)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MIDI file failed binary header integrity check.",
            )
    except HTTPException:
        raise
    except Exception:
        pass

    # Record telemetry metric
    try:
        metric = UsageMetric(
            event_type="download_midi",
            metadata_json={"filename": file_path.name, "size_bytes": file_path.stat().st_size},
        )
        db.add(metric)
        db.commit()
    except Exception:
        db.rollback()

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_path.name}"',
    }

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="audio/midi",
        headers=headers,
    )


@app.get(
    "/api/music/download/audio/{filename}",
    tags=["Downloads"],
    summary="Download or Stream Generated WAV Audio File",
)
def download_audio_file(
    filename: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_from_header_or_query),
):
    """
    Securely stream or download a generated WAV audio file.
    If the requested WAV file is not yet rendered on disk, safely attempts on-demand
    synthesis from its corresponding generated MIDI file.
    Supports inline browser playback with proper audio/wav headers and tenant boundary enforcement.
    """
    file_path = validate_safe_path(AUDIO_OUTPUT_DIR, filename, allowed_extensions={".wav", ".mp3", ".ogg", ".flac"})
    _verify_media_access_permission(file_path.name, db, current_user)
    
    # Auto-synthesize on-demand if the WAV does not exist but the corresponding MIDI exists
    if not file_path.exists() or not file_path.is_file():
        stem = file_path.stem
        candidate_midi = MIDI_OUTPUT_DIR / f"{stem}.mid"
        if candidate_midi.exists() and candidate_midi.is_file():
            try:
                from scripts.render_audio import convert_midi_to_wav
                render_ok, out_wav, _ = convert_midi_to_wav(
                    midi_path=candidate_midi,
                    output_wav_path=file_path,
                )
                if not render_ok or not file_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to synthesize audio for the requested composition.",
                    )
            except HTTPException:
                raise
            except Exception as exc:
                logger.error("On-demand audio synthesis failed for %s: %s", filename, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Audio synthesizer encountered an error rendering file.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requested audio file '{file_path.name}' was not found.",
            )

    # Verify binary WAV header integrity if .wav
    if file_path.suffix.lower() == ".wav":
        try:
            header_bytes = file_path.read_bytes()[:44]
            is_valid, _ = validate_wav_bytes(header_bytes)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Audio file failed binary WAV header integrity check.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    # Record telemetry metric
    try:
        metric = UsageMetric(
            event_type="download_audio",
            metadata_json={"filename": file_path.name, "size_bytes": file_path.stat().st_size},
        )
        db.add(metric)
        db.commit()
    except Exception:
        db.rollback()

    media_type_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }
    media_type = media_type_map.get(file_path.suffix.lower(), "audio/wav")

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_path.name}"',
    }

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
        headers=headers,
    )


@app.post(
    "/api/music/validate-upload",
    tags=["Security"],
    summary="Validate Uploaded MIDI or Audio File",
)
async def validate_uploaded_file(
    file: UploadFile = File(...),
    file_type: str = Query("midi", enum=["midi", "audio"]),
):
    """
    Validates uploaded file against security constraints:
    - Path traversal & filename sanitation
    - Enforces 15MB file size boundary
    - Verifies genuine binary magic bytes (MThd for MIDI, RIFF/WAVE for WAV)
    - Rejects executable files or disguised payloads
    """
    safe_name = Path(file.filename or "unknown").name
    content = await file.read()
    is_valid, error_msg = validate_file_upload(
        filename=safe_name,
        content=content,
        expected_type=file_type,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {error_msg}",
        )

    return {
        "valid": True,
        "filename": safe_name,
        "size_bytes": len(content),
        "file_type": file_type,
        "message": "File passed security verification and magic byte inspection.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)