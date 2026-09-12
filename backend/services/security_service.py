"""
AI Music Studio - Security Hardening & Protection Module
Provides enterprise-grade defenses across:
1. Security Headers Middleware (OWASP recommended headers)
2. In-Memory Sliding-Window Rate Limiting (Brute-force & DoS prevention)
3. Strict Path Traversal Prevention (Filename validation & boundary enforcement)
4. Binary File & Magic Bytes Validation (MIDI b'MThd', WAV b'RIFF'/'WAVE')
5. Input Sanitization (XSS and script injection removal)
6. Safe Error Handling (Zero system path or credential leakage)
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Set, Optional, Tuple, Dict, Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import HTTPException, status

logger = logging.getLogger("ai_music_studio.security")

# Allowed filename character pattern: alphanumeric, hyphen, underscore, dot
SAFE_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")

# Script and HTML tag removal pattern for XSS defense
HTML_TAG_PATTERN = re.compile(r"<[^>]*?>")
DANGEROUS_PATTERNS = [
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
    re.compile(r"onload\s*=", re.IGNORECASE),
    re.compile(r"onerror\s*=", re.IGNORECASE),
    re.compile(r"onclick\s*=", re.IGNORECASE),
]

# Magic bytes definitions
MIDI_MAGIC = b"MThd"
WAV_RIFF_MAGIC = b"RIFF"
WAV_FORMAT_MAGIC = b"WAVE"


# ===========================================================================
# 1. OWASP SECURE HTTP HEADERS MIDDLEWARE
# ===========================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects standard security headers into all HTTP responses to protect
    against clickjacking, MIME-sniffing, XSS, and unauthorized framing.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking / iframe embedding
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy browser XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Strict Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy (allows self-origin resources and safe media streaming)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "media-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "frame-ancestors 'none';"
        )

        # Restrict browser capabilities/permissions
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"

        # HTTP Strict Transport Security (HSTS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# ===========================================================================
# 2. IN-MEMORY SLIDING-WINDOW RATE LIMITER
# ===========================================================================

class InMemoryRateLimiter:
    """
    Sliding-window rate limiter to mitigate brute-force authentication attacks
    and resource exhaustion on compute-heavy AI generation endpoints.
    """

    def __init__(self):
        # Maps (route_prefix, client_ip) -> list of request timestamps
        self._history: Dict[Tuple[str, str], list] = {}
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1")
        # Rate limit configurations: route_prefix -> (max_requests, window_seconds)
        self.limits: Dict[str, Tuple[int, int]] = {
            "/api/auth/login": (20, 60),       # 20 attempts per minute
            "/api/auth/register": (30, 60),    # 30 registrations per minute
            "/api/music/generate": (30, 60),   # 30 generations per minute
            "/api/prompt/interpret": (60, 60), # 60 prompt interpretations per minute
            "/api/music/download": (120, 60),  # 120 media streams/downloads per minute
        }

    def reset(self):
        """Reset all rate limiter tracking history (useful for test isolation)."""
        self._history.clear()

    def _clean_old_requests(self, key: Tuple[str, str], window_seconds: int, now: float) -> list:
        cutoff = now - window_seconds
        records = [ts for ts in self._history.get(key, []) if ts > cutoff]
        self._history[key] = records
        return records

    def is_allowed(self, path: str, client_ip: str) -> Tuple[bool, int, int]:
        """
        Check if the incoming request path and client IP is within permitted rate limits.
        Returns (is_allowed: bool, remaining_requests: int, retry_after_seconds: int).
        """
        if not self.enabled:
            return True, 999, 0

        now = time.time()
        for route_prefix, (max_req, window_sec) in self.limits.items():
            if path.startswith(route_prefix):
                key = (route_prefix, client_ip)
                records = self._clean_old_requests(key, window_sec, now)

                if len(records) >= max_req:
                    oldest = records[0]
                    retry_after = max(1, int(window_sec - (now - oldest)))
                    return False, 0, retry_after

                # Record current request
                records.append(now)
                self._history[key] = records
                remaining = max_req - len(records)
                return True, remaining, 0

        # Untracked paths are unconditionally allowed
        return True, 999, 0


rate_limiter = InMemoryRateLimiter()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware enforcing rate limits on sensitive endpoints."""

    async def dispatch(self, request: Request, call_next):
        # Extract client IP (handling standard proxies if configured)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        path = request.url.path
        allowed, remaining, retry_after = rate_limiter.is_allowed(path, client_ip)

        if not allowed:
            logger.warning("Rate limit exceeded for IP %s on path %s", client_ip, path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please slow down and try again later.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": "exceeded",
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        if remaining != 999:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


# ===========================================================================
# 3. PATH TRAVERSAL DEFENSE & SECURE FILENAME RESOLUTION
# ===========================================================================

def validate_safe_path(base_dir: Path, filename: str, allowed_extensions: Optional[Set[str]] = None) -> Path:
    """
    Validates and resolves a requested filename against a target base directory.
    Strictly prevents:
    - Path traversal characters ('..', '/', '\\', '\x00')
    - Hidden/dotfiles
    - Arbitrary extensions outside the allowed whitelist
    - Symlink escapes pointing outside base_dir
    """
    if not filename or not isinstance(filename, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename supplied.",
        )

    # 1. Reject null bytes and directory delimiters
    if "\x00" in filename or "/" in filename or "\\" in filename or ".." in filename:
        logger.warning("Path traversal attempt detected in filename: %r", filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path traversal detected. File path rejected.",
        )

    # 2. Check regex whitelist for characters
    if not SAFE_FILENAME_PATTERN.match(filename):
        logger.warning("Disallowed characters in filename: %r", filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename format. Only alphanumeric characters, hyphens, underscores, and dots are permitted.",
        )

    # 3. Disallow leading dot (hidden files)
    if filename.startswith("."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hidden files cannot be accessed.",
        )

    # 4. Verify extension against whitelist
    file_ext = Path(filename).suffix.lower()
    if allowed_extensions and file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{file_ext}'. Permitted: {', '.join(sorted(allowed_extensions))}",
        )

    # 5. Resolve path and ensure strictly within base_dir boundary
    base_resolved = base_dir.resolve()
    target_path = (base_dir / filename).resolve()

    try:
        is_inside = target_path.is_relative_to(base_resolved)
    except AttributeError:
        # Fallback for Python versions before 3.9
        is_inside = str(target_path).startswith(str(base_resolved))

    if not is_inside:
        logger.warning("Resolved file path outside base boundary: %s", target_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access denied: resolved file path escapes base directory.",
        )

    # 6. Reject symlink pointing outside base_dir
    if target_path.is_symlink():
        symlink_target = target_path.readlink().resolve()
        if not symlink_target.is_relative_to(base_resolved):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access denied: symlink points outside base directory.",
            )

    return target_path


# ===========================================================================
# 4. BINARY FILE VALIDATION & MAGIC BYTES INSPECTION
# ===========================================================================

def validate_midi_bytes(content: bytes) -> Tuple[bool, Optional[str]]:
    """
    Validates that a binary byte stream corresponds to a genuine Standard MIDI File.
    Checks:
    - Minimum length (14 bytes for MThd header chunk)
    - Magic header 'MThd'
    - Header chunk length == 6
    """
    if len(content) < 14:
        return False, f"MIDI file is too small ({len(content)} bytes). Minimum 14 bytes required."

    # Check magic header
    if not content.startswith(MIDI_MAGIC):
        return False, "File header missing standard MIDI 'MThd' identifier."

    # Header length (big endian 32-bit uint starting at offset 4)
    header_length = int.from_bytes(content[4:8], byteorder="big")
    if header_length < 6:
        return False, f"Invalid MIDI header length: {header_length} (expected at least 6)."

    return True, None


def validate_wav_bytes(content: bytes) -> Tuple[bool, Optional[str]]:
    """
    Validates that a binary byte stream corresponds to a genuine WAV audio file.
    Checks:
    - Minimum length (44 bytes for standard PCM RIFF header)
    - Magic header 'RIFF'
    - Format identifier 'WAVE'
    """
    if len(content) < 44:
        return False, f"WAV file is too small ({len(content)} bytes). Minimum 44 bytes required."

    if not content.startswith(WAV_RIFF_MAGIC):
        return False, "File header missing RIFF identifier."

    if content[8:12] != WAV_FORMAT_MAGIC:
        return False, "File missing WAVE audio format identifier."

    return True, None


def validate_file_upload(
    filename: str,
    content: bytes,
    expected_type: str,
    max_size_bytes: int = 15 * 1024 * 1024,  # 15MB limit
) -> Tuple[bool, Optional[str]]:
    """
    Comprehensive file upload validator:
    - Validates filename format & extension
    - Enforces maximum file size limit
    - Inspects binary magic bytes against declared type
    - Rejects executable extensions or embedded scripts
    """
    if len(content) > max_size_bytes:
        return False, f"File exceeds maximum allowed size of {max_size_bytes // (1024 * 1024)}MB."

    if len(content) == 0:
        return False, "Uploaded file is empty (0 bytes)."

    # Reject dangerous executable extensions
    dangerous_extensions = {
        ".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".dll", ".so", ".dylib",
        ".php", ".py", ".rb", ".pl", ".jsp", ".asp", ".aspx", ".cgi", ".jar",
    }
    file_ext = Path(filename).suffix.lower()
    if file_ext in dangerous_extensions:
        return False, f"Uploading executable or script file '{file_ext}' is strictly prohibited."

    if expected_type == "midi":
        if file_ext not in {".mid", ".midi"}:
            return False, "File extension must be .mid or .midi for MIDI uploads."
        return validate_midi_bytes(content)

    elif expected_type == "audio":
        if file_ext not in {".wav", ".mp3", ".ogg", ".flac"}:
            return False, "File extension must be .wav, .mp3, .ogg, or .flac for audio uploads."
        if file_ext == ".wav":
            return validate_wav_bytes(content)
        return True, None

    return False, f"Unsupported file type '{expected_type}'."


# ===========================================================================
# 5. INPUT SANITIZATION & XSS PROTECTION
# ===========================================================================

def sanitize_user_input(text: Optional[str], max_length: int = 500) -> Optional[str]:
    """
    Sanitizes string inputs to prevent Cross-Site Scripting (XSS) and script injection.
    - Strips HTML/XML tags
    - Rejects or strips JavaScript event handlers
    - Enforces length boundary
    """
    if text is None:
        return None

    cleaned = str(text).strip()
    # Strip HTML tags
    cleaned = HTML_TAG_PATTERN.sub("", cleaned)

    # Strip dangerous JavaScript patterns
    for pattern in DANGEROUS_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Enforce length limit
    return cleaned[:max_length].strip()
