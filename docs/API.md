# AI Music Studio — REST API Documentation

**API Version:** `1.0.0`  
**Base URL:** `http://localhost:8000`  
**Interactive Documentation:**
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON Schema:** `http://localhost:8000/openapi.json`

---

## 1. Authentication Architecture

AI Music Studio uses **Bearer JSON Web Tokens (JWT)** for authentication and Role-Based Access Control (RBAC).

### Authorization Header
To access protected endpoints, pass the token in the standard HTTP `Authorization` header:
```http
Authorization: Bearer <your_access_token>
```

### Roles & Permissions
| Role | Description | Access Scope |
|---|---|---|
| **Public / Guest** | Unauthenticated user | Health check, public music generation, asset downloads, feedback |
| **USER** | Registered music creator | All guest capabilities + private generation history and project isolation |
| **ADMIN** | Studio administrator | All USER capabilities + administrative telemetry, global logs, feedback & error oversight |

---

## 2. Table of Endpoints

| Category | Method | Endpoint | Auth Required | Description |
|---|---|---|---|---|
| **System** | `GET` | `/` | None | Root status info |
| **System** | `GET` | `/health` | None | System, database & ML health check |
| **Auth** | `POST` | `/api/auth/register` | None | Register a new creator account |
| **Auth** | `POST` | `/api/auth/login` | None | Authenticate and obtain JWT token |
| **Auth** | `GET` | `/api/auth/me` | USER / ADMIN | Get profile of current user |
| **Auth** | `POST` | `/api/auth/logout` | None | Invalidate client session |
| **Prompt** | `POST` | `/api/prompt/interpret` | None | Parse natural language to parameters via Groq |
| **Generation** | `POST` | `/api/music/generate` | Optional | End-to-end music generation |
| **History** | `GET` | `/api/generations` | Optional | User-isolated generation history |
| **History** | `GET` | `/api/generations/{id}` | Optional (Isolated)| Get single generation detail |
| **Feedback** | `POST` | `/api/feedback` | None | Submit 1–5 star rating and comment |
| **Downloads** | `GET` | `/api/music/download/midi/{filename}`| None | Stream / download MIDI file |
| **Downloads** | `GET` | `/api/music/download/audio/{filename}`| None | Stream / download WAV audio file |
| **Security** | `POST` | `/api/music/validate-upload`| None | Validate MIDI/WAV upload headers |
| **Admin** | `GET` | `/api/admin/dashboard` | ADMIN | Comprehensive live telemetry dashboard |
| **Admin** | `GET` | `/api/admin/metrics` | ADMIN | Summary statistics |
| **Admin** | `GET` | `/api/admin/generations` | ADMIN | Global generation audit logs |
| **Admin** | `GET` | `/api/admin/users` | ADMIN | Registered creator user directory |
| **Admin** | `GET` | `/api/admin/feedback` | ADMIN | Global user feedback directory |
| **Admin** | `GET` | `/api/admin/errors` | ADMIN | System error & failure telemetry |

---

## 3. Detailed Endpoint Specifications

### 3.1 `GET /health`
Verifies backend service availability, database connectivity, and ML engine readiness.

- **Method:** `GET`
- **Authentication:** None
- **Request Body:** None
- **Success Status Code:** `200 OK`

#### Example Request:
```bash
curl -X GET "http://localhost:8000/health"
```

#### Example Response (`200 OK`):
```json
{
  "status": "healthy",
  "service": "AI Music Studio Backend",
  "environment": "development",
  "components": {
    "api": "ok",
    "database": "ok",
    "groq_prompt_parser": "groq_api_ready",
    "ai_engine": "lstm_v1_ready",
    "auth_security": "jwt_bcrypt_active"
  }
}
```

---

### 3.2 `POST /api/auth/register`
Creates a new creator account with secure bcrypt password hashing.

- **Method:** `POST`
- **Authentication:** None
- **Rate Limit:** 10 requests / minute
- **Success Status Code:** `201 Created`
- **Error Status Codes:**
  - `400 Bad Request`: Username or email already registered
  - `422 Unprocessable Entity`: Validation error (password < 8 chars, invalid email)

#### Request Body (`UserRegisterRequest`):
| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `username` | string | Yes | 3–32 chars, alphanumeric + `_` | Unique creator username |
| `email` | string | Yes | Valid email format | Unique email address |
| `password` | string | Yes | Min 8 chars, max 128 chars | Plaintext password |
| `role` | string | No | `"USER"` or `"ADMIN"` (default: `"USER"`) | Account authorization tier |

#### Example Request:
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "mozart_ai",
    "email": "mozart@studio.ai",
    "password": "SuperSecretPassword123!",
    "role": "USER"
  }'
```

#### Example Response (`201 Created`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_seconds": 86400,
  "user": {
    "id": "u_e534f2d7-b891-4927-a044-f17e29cb115a",
    "username": "mozart_ai",
    "email": "mozart@studio.ai",
    "role": "USER",
    "is_active": true,
    "created_at": "2026-09-11T20:15:30Z"
  }
}
```

---

### 3.3 `POST /api/auth/login`
Authenticates a user via credentials and issues a signed JWT access token.

- **Method:** `POST`
- **Authentication:** None
- **Rate Limit:** 10 requests / minute (Brute-force protection)
- **Success Status Code:** `200 OK`
- **Error Status Codes:**
  - `401 Unauthorized`: Invalid credentials
  - `403 Forbidden`: Account deactivated
  - `429 Too Many Requests`: Rate limit exceeded

#### Request Body (`UserLoginRequest`):
```json
{
  "username": "mozart_ai",
  "password": "SuperSecretPassword123!"
}
```

#### Example Response (`200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in_seconds": 86400,
  "user": {
    "id": "u_e534f2d7-b891-4927-a044-f17e29cb115a",
    "username": "mozart_ai",
    "email": "mozart@studio.ai",
    "role": "USER",
    "is_active": true,
    "created_at": "2026-09-11T20:15:30Z"
  }
}
```

---

### 3.4 `GET /api/auth/me`
Retrieves account details for the authenticated user.

- **Method:** `GET`
- **Authentication:** `Bearer <token>` (Required)
- **Success Status Code:** `200 OK`
- **Error Status Codes:**
  - `401 Unauthorized`: Missing, expired, or invalid token

#### Example Request:
```bash
curl -X GET "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer <token>"
```

#### Example Response (`200 OK`):
```json
{
  "id": "u_e534f2d7-b891-4927-a044-f17e29cb115a",
  "username": "mozart_ai",
  "email": "mozart@studio.ai",
  "role": "USER",
  "is_active": true,
  "created_at": "2026-09-11T20:15:30Z"
}
```

---

### 3.5 `POST /api/auth/logout`
Terminates user session and signals client token clearance.

- **Method:** `POST`
- **Authentication:** Optional
- **Success Status Code:** `200 OK`

#### Example Response:
```json
{
  "success": true,
  "message": "Logged out successfully."
}
```

---

### 3.6 `POST /api/music/generate`
The core symbolic music composition and synthesis pipeline.

Accepts either natural language (`prompt`), explicit advanced controls (`mood`, `instrument`, `tempo`, `musicalKey`, etc.), or a hybrid combination. Explicit controls strictly override prompt suggestions.

- **Method:** `POST`
- **Authentication:** Optional (Automatically associates generation with creator if token provided)
- **Rate Limit:** 30 requests / minute
- **Success Status Code:** `200 OK`
- **Error Status Codes:**
  - `422 Unprocessable Entity`: Missing both prompt and controls, or invalid range
  - `500 Internal Server Error`: Safe generic error message on pipeline failure
  - `503 Service Unavailable`: Model weights missing or offline

#### Request Body (`MusicGenerateRequest`):
| Field | Type | Required | Default | Range / Allowed Values | Description |
|---|---|---|---|---|---|
| `prompt` | string | No | `null` | Max 500 chars | Natural language description |
| `render_audio` | boolean | No | `true` | `true`, `false` | Synthesize playable WAV audio |
| `mood` | string | No | `null` | peaceful, energetic, melancholic, etc. | Musical sentiment |
| `instrument` | string | No | `null` | piano, violin, acoustic guitar, etc. | Lead instrument |
| `tempo` | float | No | `null` | 40.0 – 240.0 BPM | Explicit speed in BPM |
| `duration_seconds` | integer | No | `60` | 15 – 240 | Desired track length |
| `complexity` | string | No | `null` | `"low"`, `"medium"`, `"high"` | Polyphonic density |
| `key` | string | No | `null` | C, C#, D, D#, E, F, F#, G, G#, A, A#, B | Root musical key |
| `scale` | string | No | `null` | `"major"`, `"minor"` | Tonality scale mode |
| `temperature` | float | No | `0.85` | 0.1 – 2.0 | Sampling creativity |
| `random_seed` | integer | No | `null` | Any 32-bit int | Deterministic seed |

#### Example Request:
```bash
curl -X POST "http://localhost:8000/api/music/generate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Peaceful piano music for meditation at 70 BPM",
    "render_audio": true,
    "mood": "peaceful",
    "instrument": "piano",
    "tempo": 70,
    "temperature": 0.8
  }'
```

#### Example Response (`200 OK`):
```json
{
  "success": true,
  "generation_id": "gen_84d12c9b4e10",
  "metadata": {
    "prompt": "Peaceful piano music for meditation at 70 BPM",
    "interpreted_parameters": {
      "mood": "peaceful",
      "instrument": "piano",
      "style": "meditation",
      "tempo": 70.0,
      "complexity": "low",
      "energy": "low",
      "duration_seconds": 60
    },
    "user_overrides_applied": {
      "mood": "peaceful",
      "instrument": "piano",
      "tempo": 70.0
    },
    "model_version": "lstm_v1",
    "temperature_used": 0.8,
    "random_seed_used": 194208451,
    "num_events_generated": 50,
    "duration_quarter_lengths": 25.0,
    "notes_count": 34,
    "chords_count": 8,
    "rests_count": 8,
    "tempo_bpm": 70.0,
    "instrument": "piano",
    "key": "C",
    "scale": "major",
    "generation_duration_ms": 485
  },
  "midi_file": {
    "filename": "studio_gen_84d12c9b4e10.mid",
    "download_url": "/api/music/download/midi/studio_gen_84d12c9b4e10.mid",
    "file_type": "midi",
    "size_bytes": 1042
  },
  "audio_file": {
    "filename": "studio_gen_84d12c9b4e10.wav",
    "download_url": "/api/music/download/audio/studio_gen_84d12c9b4e10.wav",
    "file_type": "audio",
    "size_bytes": 84520
  },
  "audio_status": "rendered",
  "message": "Music composition and synthesis completed successfully."
}
```

---

### 3.7 `GET /api/generations`
Retrieves paginated generation history with strict user data isolation.

- **Method:** `GET`
- **Authentication:** Optional
- **Query Parameters:**
  - `page`: integer (default `1`, $\ge 1$)
  - `limit`: integer (default `20`, range `1–100`)
- **Access Scope:**
  - Authenticated `USER`: Sees **only their own** generated music.
  - Authenticated `ADMIN`: Sees **all** system generations.
  - Unauthenticated Guest: Sees recent public/guest generations.
- **Success Status Code:** `200 OK`

#### Example Request:
```bash
curl -X GET "http://localhost:8000/api/generations?page=1&limit=10" \
  -H "Authorization: Bearer <token>"
```

#### Example Response (`200 OK`):
```json
{
  "total": 1,
  "page": 1,
  "limit": 10,
  "items": [
    {
      "id": "gen_rec_91a0c8b2-4d71",
      "generation_id": "gen_84d12c9b4e10",
      "prompt": "Peaceful piano music for meditation at 70 BPM",
      "model_version": "lstm_v1",
      "tempo_bpm": 70.0,
      "instrument": "piano",
      "musical_key": "C",
      "scale": "major",
      "temperature": 0.8,
      "generation_status": "completed",
      "generation_duration_ms": 485,
      "midi_file": {
        "filename": "studio_gen_84d12c9b4e10.mid",
        "download_url": "/api/music/download/midi/studio_gen_84d12c9b4e10.mid",
        "file_type": "midi",
        "size_bytes": 1042
      },
      "audio_file": {
        "filename": "studio_gen_84d12c9b4e10.wav",
        "download_url": "/api/music/download/audio/studio_gen_84d12c9b4e10.wav",
        "file_type": "audio",
        "size_bytes": 84520
      },
      "created_at": "2026-09-11T20:25:00Z"
    }
  ]
}
```

---

### 3.8 `GET /api/generations/{id}`
Retrieves complete details of a specific composition by ID.

- **Method:** `GET`
- **Authentication:** Optional (Enforced when record belongs to a registered creator)
- **Path Parameter:** `id` (database UUID or `generation_id` string)
- **Success Status Code:** `200 OK`
- **Error Status Codes:**
  - `401 Unauthorized`: Authentication required for private generation
  - `403 Forbidden`: User attempts to view another creator's generation
  - `404 Not Found`: Record does not exist

#### Example Request:
```bash
curl -X GET "http://localhost:8000/api/generations/gen_84d12c9b4e10" \
  -H "Authorization: Bearer <token>"
```

---

### 3.9 `POST /api/feedback`
Submits user sentiment, rating, and optional commentary for future model evaluation.

- **Method:** `POST`
- **Authentication:** Optional
- **Success Status Code:** `200 OK`
- **Error Status Codes:**
  - `404 Not Found`: Target generation ID does not exist
  - `422 Unprocessable Entity`: Rating not between 1 and 5

#### Request Body (`FeedbackSubmitRequest`):
```json
{
  "generation_id": "gen_84d12c9b4e10",
  "rating": 5,
  "is_liked": true,
  "comment": "The harmony and tempo progression was very relaxing."
}
```

#### Example Response (`200 OK`):
```json
{
  "success": true,
  "feedback_id": "fb_312f00a8-b991-4560-84c1-6bce40182",
  "message": "Thank you! Your feedback has been recorded."
}
```

---

### 3.10 `GET /api/music/download/midi/{filename}` & `GET /api/music/download/audio/{filename}`
Streams and downloads validated MIDI and synthesized WAV audio files.

- **Method:** `GET`
- **Authentication:** None
- **Security Protections:**
  - Rejects path traversal (`..`, null bytes, slashes)
  - Inspects file existence in strict isolated directories
  - Validates binary magic byte headers (`MThd` for MIDI, `RIFF`/`WAVE` for audio)
- **Success Status Code:** `200 OK` (Streams `audio/midi` or `audio/wav`)
- **Error Status Codes:**
  - `400 Bad Request`: Malformed or path traversal filename
  - `404 Not Found`: File not found
  - `422 Unprocessable Entity`: File failed binary header check

---

### 3.11 Admin Endpoints (Role: `ADMIN` Only)

All endpoints in this section strictly require an authenticated user with `role="ADMIN"`. Attempts by unauthenticated users return `401 Unauthorized`; attempts by standard `USER` accounts return `403 Forbidden`.

#### `GET /api/admin/dashboard`
Returns live system intelligence including total users, generation telemetry today, breakdown of successful vs failed generations, dataset verification status, common feedback keywords, and error distributions.

```bash
curl -X GET "http://localhost:8000/api/admin/dashboard" \
  -H "Authorization: Bearer <admin_token>"
```

#### `GET /api/admin/metrics`
Returns core administrative counts:
```json
{
  "admin_username": "admin",
  "total_registered_users": 15,
  "total_generations": 142,
  "completed_generations": 139,
  "model_version": "lstm_v1",
  "system_status": "optimal"
}
```

#### `GET /api/admin/generations`
Paginated log of all compositions across all creators with optional `status` filter (`?status=completed`).

#### `GET /api/admin/users`
Directory of all registered creator accounts, roles, and registration timestamps.

#### `GET /api/admin/feedback`
Directory of all recorded ratings, like/dislike votes, and user comments.

#### `GET /api/admin/errors`
Directory of failed generations with associated error messages and prompts for model evaluation.

---

## 4. Standard Error Response Format

All error responses return consistent, sanitized JSON payloads complying with FastAPI standards. Raw stack traces and internal machine paths are **never exposed**:

```json
{
  "detail": "Descriptive, safe explanation of the error."
}
```

### Standard Status Codes
| HTTP Code | Name | Typical Cause |
|---|---|---|
| `200` | OK | Request succeeded |
| `201` | Created | Resource successfully created (registration, feedback) |
| `400` | Bad Request | Duplicate registration, invalid input |
| `401` | Unauthorized | Missing or expired JWT token |
| `403` | Forbidden | Insufficient role permissions (e.g. USER accessing admin) |
| `404` | Not Found | Generation or file does not exist |
| `422` | Unprocessable Entity | Pydantic schema validation failure or corrupted binary header |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Sanitized generic internal error |
| `503` | Service Unavailable | Model or downstream service offline |

---

## 5. Security & Rate Limiting Overview

- **Rate Limits:**
  - Login & Registration: **10 requests / minute / IP**
  - Music Generation: **30 requests / minute / IP**
  - Prompt Interpretation: **60 requests / minute / IP**
  - General Endpoints: **120 requests / minute / IP**
- **OWASP Headers:**
  - `Content-Security-Policy`
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Strict-Transport-Security: max-age=31536000`
  - `Referrer-Policy: strict-origin-when-cross-origin`
