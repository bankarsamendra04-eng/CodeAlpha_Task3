# AI Music Studio

![GitHub license](https://img.shields.io/badge/license-MIT-blue.svg)

**AI Music Studio** is a full‑stack web application that generates original polyphonic music using a trained MAESTRO LSTM model. Users can describe music in natural language or fine‑tune parameters (instrument, tempo, mood, etc.). The system synthesises a MIDI file and renders a high‑quality WAV audio file that can be streamed in‑app or downloaded.

---

## 📖 Project Overview

- **Web UI** built with **React** (Vite) for an interactive studio experience.
- **Backend** powered by **FastAPI** (Python) exposing secure JWT‑based APIs.
- **Music generation** using a **MAESTRO LSTM** model (trained on the MAESTRO dataset).
- **Roles**: `USER` – normal music creation; `ADMIN` – system metrics & admin dashboard.
- **Database**: SQLite (development) with SQLAlchemy ORM, storing users, generation history, feedback, and usage metrics.

---

## ✨ Key Features

| Feature | Description |
|--------|-------------|
| 🎹 Music Generation | Natural‑language prompt → LSTM token generation → MIDI → WAV audio |
| 🎧 In‑app Playback | Stream generated WAV with HTML5 `<audio>` element (supports play/pause, seek, volume) |
| 📥 Download | Download MIDI and WAV files for offline use |
| 🔐 Secure Auth | JWT authentication, bcrypt‑hashed passwords, role‑based access control |
| 📊 Admin Dashboard | View system health, usage metrics, and manage users |
| 📜 History | Persist generation records per user, view and replay past tracks |
| 📱 Responsive UI | Works on desktop browsers, with loading states and error handling |

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, Vite, Tailwind CSS |
| Backend | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Database | SQLite (dev) – can be swapped for PostgreSQL |
| Model | MAESTRO LSTM (15 M parameters) |
| Auth | JWT, bcrypt |
| Dev / Deploy | Docker, Docker‑Compose |

---

## 📐 Architecture & Workflow

1. **User** logs in (or registers) → receives JWT token.
2. **Prompt** (text + optional controls) is sent to `/api/music/generate`.
3. Backend **parses** prompt (optionally via Groq API) and feeds parameters to the LSTM model.
4. Model **generates** a symbolic MIDI sequence → saved to `output/`.
5. **Audio rendering** converts MIDI → WAV (via `music21` + `FluidSynth`).
6. Generated files are stored and a **record** is saved in the DB.
7. Frontend displays **metadata**, an **audio player**, and a **download** button.
8. **History** endpoint allows users to reload past tracks; admin endpoints expose metrics.

---

## 📂 Project Structure

```
AI-Music-Studio/
├─ backend/                 # FastAPI application
│  ├─ main.py               # API entry point
│  ├─ services/            # Auth, security, generation, etc.
│  ├─ schemas/             # Pydantic models
│  └─ database/            # SQLAlchemy models & connection
├─ frontend/                # React application
│  ├─ src/App.jsx          # Main UI logic (includes audio player)
│  └─ public/              # Static assets
├─ docs/                    # Design docs, API spec, architecture
├─ output/                  # Generated MIDI/WAV files (runtime)
├─ .env.example            # Example env variables (safe placeholders)
├─ .gitignore               # Ignored files & directories
└─ README.md                # This document
```

---

## 🚀 Installation & Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 20+** (for the frontend)
- **Git**
- **Docker** (optional, for containerised run)

### 1️⃣ Clone the repository
```bash
git clone https://github.com/bankarsamendra04-eng/CodeAlpha_Task3.git
cd CodeAlpha_Task3/AI-Music-Studio
```

### 2️⃣ Set up the Python backend
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Set up the React frontend
```bash
cd frontend
npm install
```

### 4️⃣ Create an `.env` file
Copy the example and fill in your own secrets:
```bash
cp .env.example .env
# Edit .env with your own values (GROQ_API_KEY, SECRET_KEY, etc.)
```

### 5️⃣ Initialise the database
```bash
python -c "from backend.database.connection import init_db; init_db()"
```

### 6️⃣ Run the application
#### Backend
```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
#### Frontend
```bash
cd frontend
npm run dev   # Vite dev server (http://localhost:5173)
```
Open the UI in a browser and start generating music!

---

## 🔐 Authentication & Roles
- **Registration** → USER role assigned automatically.
- **Admin** account is seeded securely via the `admin_seed.py` script (see `backend/services/admin_service.py`).
- JWT token stored in `localStorage` (`aimusic_token`).
- Protected endpoints enforce `role == "ADMIN"` where required.

---

## 🎶 Music Generation & Playback
- **Prompt → LSTM → MIDI** (stored under `output/`)
- **MIDI → WAV** using `music21` + FluidSynth.
- Audio is streamed via `/api/music/download/audio/<filename>` (requires auth).
- The UI uses an `<audio>` element with play/pause, seek, and volume controls.

---

## 📡 API Overview
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/register` | POST | ❌ | Create a new USER account |
| `/api/auth/login` | POST | ❌ | Obtain JWT token |
| `/api/music/generate` | POST | ✅ | Generate music (MIDI & WAV) |
| `/api/music/download/audio/{filename}` | GET | ✅ | Stream generated WAV |
| `/api/music/download/midi/{filename}` | GET | ✅ | Download MIDI |
| `/api/generations` | GET | ✅ | List user history |
| `/api/admin/dashboard` | GET | ✅ (ADMIN) | System metrics |

See `docs/API.md` for full OpenAPI spec.

---

## 🧪 Testing
```bash
pytest tests/      # Run backend unit/integration tests
npm run test       # Frontend tests (if any)
```
All tests pass locally.

---

## 🔒 Security Notes
- **Passwords** are never stored in plaintext – bcrypt hashing.
- **JWT secret** (`SECRET_KEY`) must be rotated in production.
- **CORS** limited to known origins.
- **Rate limiting** and security‑header middleware are enabled.
- **`.env`** is excluded via `.gitignore`.

---

## 📈 Future Improvements
- Add **WebSocket** streaming for real‑time generation progress.
- Containerise the **frontend** with Nginx for production.
- Swap SQLite for a managed PostgreSQL database.
- Implement **OAuth** login options.
- Add **unit tests** for the audio rendering pipeline.

---

## 👤 Author & Contributions
- **Samendra Bankar** – Full‑stack development, AI model integration, security hardening.
- Contributions are welcome – feel free to open PRs.

---

## 📄 License
This project is licensed under the **MIT License** – see `LICENSE` for details.
