# AI Music Studio — Enterprise Security Architecture & Hardening Guide

## Overview

AI Music Studio implements defense-in-depth security engineered for production deployment. The system adheres to OWASP guidelines, strict principle of least privilege, zero-trust tenant data isolation, and comprehensive input/output validation across both generative AI pipelines and traditional web endpoints.

---

## Security Dimensions & Defensive Controls

### 1. API Key Protection
- **Storage**: Third-party API keys (e.g. `GROQ_API_KEY`) are stored exclusively in root `.env` files or injected via secure server-side environment variables.
- **Frontend Isolation**: The React/Vite client codebase contains zero API keys or secrets. All calls to Groq are brokered strictly via the backend service (`backend/services/groq_service.py`).
- **Telemetry Sanitization**: System metrics, health checks (`/health`), and admin oversight endpoints never return or expose active keys or tokens.

### 2. Environment Variables & Secret Configuration
- **Version Control Exclusions**: Sensitive configuration files (`.env`, `*.key`, `*.pem`, `*.db`) are strictly excluded in `.gitignore`.
- **Reference Templates**: Standardized `.env.example` is maintained with placeholder documentation without real secrets.
- **Safe Fallback**: In the absence of third-party API keys, services degrade gracefully (e.g. engaging local heuristic musicologist rule engines) rather than halting or crashing.

### 3. Authentication
- **Token Format**: Stateless JSON Web Tokens (JWT) signed with HMAC-SHA256 (`HS256`).
- **Expiration Enforcement**: Access tokens feature configurable expiration timestamps (`exp` claim, defaulting to 24 hours).
- **Client Handling**: Bearer token authentication via standard HTTP `Authorization: Bearer <token>` headers.
- **Revocation / Invalidation**: User account activation status (`is_active`) is validated against the database on each authenticated request.

### 4. Authorization & Role-Based Access Control (RBAC)
- **Role Hierarchy**: Two distinct roles are enforced: `USER` and `ADMIN`.
- **Endpoint Protection**:
  - `/api/admin/*`: Strictly guarded by `require_admin` dependency; non-admin users receive `403 Forbidden`.
  - `/api/generations`: Enforces strict tenant isolation. Standard users can only list and inspect their own compositions; public guest users cannot view private user compositions.
  - Ownership Boundaries: Users cannot access another creator's generation by guessing IDs.

### 5. Password Hashing & Storage
- **Algorithm**: Native `bcrypt` using 12 salt rounds (`gensalt(12)`).
- **Plaintext Elimination**: Plaintext passwords are never persisted to disk, never cached, and never returned in API response models (`UserResponse` explicitly omits `hashed_password`).
- **Bcrypt Truncation Defense**: Plaintext passwords are automatically truncated to 72 bytes before hashing to prevent overflow exploits.

### 6. Input Validation & Schema Enforcement
- **Validation Engine**: Pydantic v2 schemas across all request bodies (`backend/schemas/`).
- **Range & Boundary Clamping**:
  - `tempo`: Enforced between 40.0 and 240.0 BPM.
  - `duration_seconds`: Enforced between 10 and 600 seconds.
  - `temperature`: Clamped between 0.1 and 2.0.
  - `prompt`: String length constrained between 3 and 500 characters.
  - `rating`: Bounded strictly between 1 and 5.
- **Username Charset**: Whitelisted to alphanumeric, hyphen, underscore, and period (`^[a-zA-Z0-9_\-\.]{3,50}$`).

### 7. File Upload Validation
- **Endpoint**: `POST /api/music/validate-upload`
- **Size Boundary**: Maximum upload limit of 15 MB enforced.
- **Extension Filtering**: Executable extensions (`.exe`, `.bat`, `.cmd`, `.sh`, `.ps1`, `.dll`, `.py`, `.php`) are immediately rejected.
- **Deep Inspection**: Validates binary magic byte headers before saving or processing.

### 8. Path Traversal Protection
- **Boundary Verification**: Download endpoints (`/api/music/download/midi/{filename}` and `/api/music/download/audio/{filename}`) employ `validate_safe_path()`:
  - Rejects traversal sequences (`..`, `/`, `\`, and null bytes `\x00` or `%00`).
  - Enforces strict character whitelist: `^[a-zA-Z0-9_\-\.]+$`.
  - Rejects hidden/dotfiles (`.env`, `.git`).
  - Resolves target paths via `Path.resolve()` and cryptographically asserts `target_path.is_relative_to(base_dir.resolve())`.
  - Rejects symlink targets resolving outside the designated output directory.

### 9. MIDI File Validation
- **Chunk Verification**: Checks that uploaded or exported MIDI data begins with the standard 4-byte identifier `b'MThd'`.
- **Header Structure**: Confirms minimal header length (at least 14 bytes) and format chunk length (`>= 6`).
- **Score Integrity**: Validated via `music21.converter.parse` verifying non-zero notes, chords, and valid musical quarter lengths.

### 10. Audio File Validation
- **Container Structure**: WAV audio files are checked for the canonical `b'RIFF'` identifier and `b'WAVE'` format chunk with `b'fmt '`.
- **Header Length**: Minimum 44-byte PCM header enforcement.
- **Format Verification**: `scripts/render_audio.py` uses Python's standard `wave` library to confirm non-zero audio frames, valid sample rates (>= 8000 Hz), and supported channel configurations (mono or stereo).

### 11. Cross-Origin Resource Sharing (CORS)
- **Origin Whitelist**: Configurable via `ALLOWED_ORIGINS` environment variable, defaulting to trusted local development origins (`http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`).
- **No Wildcard with Credentials**: Wildcard `*` origins are prohibited when `allow_credentials=True`.

### 12. Rate Limiting & Abuse Prevention
- **Architecture**: In-memory sliding-window rate limiter (`RateLimiterMiddleware`).
- **Thresholds**:
  - `/api/auth/login`: 20 requests per 60 seconds (prevents credential stuffing / brute force).
  - `/api/auth/register`: 30 registrations per 60 seconds (prevents automated account spam).
  - `/api/music/generate`: 30 requests per 60 seconds (prevents AI compute resource exhaustion).
  - `/api/prompt/interpret`: 60 requests per 60 seconds (prevents Groq quota exhaustion).
- **Response**: Exceeding requests receive `HTTP 429 Too Many Requests` with a standard `Retry-After` header.

### 13. Safe Error Handling & Information Leakage Prevention
- **Global Exception Interceptor**: FastAPI unhandled exception middleware catches raw exceptions and returns generic client-facing messages (`"An internal server error occurred. Please contact the administrator."`).
- **Path Sanitization**: Stack traces, server directory paths (e.g. `C:\Users\...` or `/home/...`), and internal module names are never disclosed in HTTP responses.
- **Detailed Server Logs**: Full diagnostic tracebacks are logged exclusively on the server side via Python's standard logging facility.

### 14. SQL Injection Protection
- **Object-Relational Mapping**: All database queries utilize SQLAlchemy ORM with strictly parameterized bindings (`db.query(User).filter(...)`).
- **Zero Raw Query Interpolation**: Raw string concatenation (`f"SELECT * FROM ... {user_input}"`) is strictly forbidden across the codebase.

### 15. Cross-Site Scripting (XSS) Protection
- **Input Sanitization**: All user-submitted prompts and feedback comments pass through `sanitize_user_input()`, which strips HTML tags (`<script>`, `<iframe>`, `<style>`) and dangerous JavaScript event handlers (`onload=`, `onerror=`, `onclick=`).
- **Frontend Escaping**: The React UI safely escapes dynamic data bindings by default in JSX.
- **Browser Protection**: Injected `X-XSS-Protection: 1; mode=block` response header.

### 16. Cross-Site Request Forgery (CSRF) Protection
- **Bearer Token Pattern**: Authentication relies on client-stored JWT tokens passed in the `Authorization: Bearer <token>` HTTP header, completely immune to standard cookie-based CSRF exploitation.
- **Origin Validation**: CORS middleware validates `Origin` and `Referer` headers on cross-origin requests.

### 17. Secure HTTP Headers
Every HTTP response includes standard OWASP recommended security headers:
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; img-src 'self' data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none';
Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=()
```

### 18. Secret Leakage in Logs
- **Credential Masking**: Log messages never output `password`, `hashed_password`, `access_token`, or database connection strings.
- **Exception Masking**: API call exceptions to Groq log only the exception type (`type(exc).__name__`), never raw HTTP requests or authorization headers.

### 19. Production Debug Configuration
- **Debug Flag**: FastAPI's `debug` parameter is driven by `os.getenv("DEBUG", "False")`, defaulting to `False` in production.
- **Reloading Disabled**: Production startup scripts run without `--reload`.

### 20. Dependency Vulnerability Management
- **Audit Compliance**: All production dependencies in `requirements.txt` specify minimum supported security versions.
- **Regular Audits**: Automated checks with test coverage ensure compatibility and integrity across core scientific and web libraries.

---

## Security Verification Test Matrix

A dedicated test suite in `tests/test_security.py` programmatically tests and verifies these hardening measures:

| Test Case | Description | Verification Method | Status |
|---|---|---|---|
| `test_security_http_headers_present` | Validates presence of nosniff, DENY, CSP, HSTS, and XSS headers | HTTP Client Response Inspection | Passed |
| `test_rate_limiting_on_auth_login` | Validates rate limit enforcement, 429 status code, and `Retry-After` header | Simulated high-frequency requests | Passed |
| `test_path_traversal_rejection` | Attempts path traversal attacks (`..`, Windows backslashes, percent-encoded, null bytes) | Download Route Execution | Passed |
| `test_safe_path_validation_logic` | Validates `validate_safe_path()` against disallowed extensions and hidden files | Direct Unit Assertion | Passed |
| `test_validate_midi_bytes` | Validates `b'MThd'` header chunk integrity on valid and corrupted MIDI streams | Binary Inspection | Passed |
| `test_validate_wav_bytes` | Validates `b'RIFF'` and `b'WAVE'` chunk validation on audio streams | Binary Inspection | Passed |
| `test_file_upload_validation_endpoint` | Uploads valid MIDI vs disguised `.exe` malware | Multipart Upload Endpoint | Passed |
| `test_input_sanitization` | Injects `<script>` and event handlers into text inputs | Sanitization Assertions | Passed |
| `test_safe_error_messages_no_stacktrace` | Triggers error responses and asserts zero system path leakage | Response Body Inspection | Passed |
| `test_api_keys_and_passwords_never_exposed` | Checks `/health` and metadata endpoints for secret leakage | Secret Pattern Matching | Passed |
| `test_sql_injection_resistance` | Attempts SQL injection syntax payloads against entity routes | ORM Parameterization Assertion | Passed |

---

## Conclusion & Deployment Checklist

Before deploying AI Music Studio to a production public server:
1. Generate a high-entropy `SECRET_KEY` (minimum 32 bytes):
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Set `DEBUG=False` in `.env`.
3. Set `ALLOWED_ORIGINS` to your production domain(s).
4. Supply your valid `GROQ_API_KEY` in `.env`.
5. Bind Uvicorn behind a reverse proxy (Nginx / Caddy / Cloudflare) with TLS 1.3 termination.
