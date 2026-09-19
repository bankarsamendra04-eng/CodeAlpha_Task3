# AI Music Studio - Local Environment Setup & Operational Guide

This document outlines the complete environment setup, hardware offloading architecture (E: Drive utilization), dependency installation, runtime patches, and operational procedures for **AI Music Studio** on Windows.

---

## 💻 Machine & Host Environment Specifications

- **Operating System:** Windows 11 Home Single Language (64-bit, Version 10.0.26200)
- **Primary Storage (C:):** OS & User Profile
- **Development Workspaces (D:):** `D:\Projects\CodAlpha Task 3\AI-Music-Studio`
- **High-Capacity Secondary Drive (E:):** `E:\banka\Development\`
- **Python Version:** Python 3.11.9 (64-bit)
- **Node.js Runtime:** v24.21.0 (with npm 11.8.0)
- **Deep Learning Framework:** TensorFlow 2.21.0 & Keras 3.15.1
- **Symbolic Music Toolkit:** Music21 10.5.0
- **Web APIs & Server:** FastAPI 0.141.1 & Uvicorn 0.53.0
- **Frontend Stack:** React 18, Vite 5.4.21, Tailwind CSS, Lucide Icons

---

## 🗄️ E: Drive Offloading Architecture

To conserve space and avoid polluting system paths, heavy SDKs, caches, virtual environments, and artifacts are mapped to the high-capacity `E:` drive under `E:\banka\Development\`:

```text
E:\banka\Development\
├── VirtualEnvironments\
│   └── ai_music_studio_venv\       <-- Full Python 3.11 isolated environment (~1.8 GB)
├── Caches\
│   ├── pip\                        <-- Pip download cache
│   └── npm\                        <-- Npm package cache
├── Models\                         <-- Pre-trained checkpoints and weights
├── Datasets\                       <-- MAESTRO dataset cache and splits
└── Tools\
    └── vcredist_dlls\              <-- MSVC C++ 14.x x64 runtime redistributables
```

### NTFS Directory Junction
An NTFS junction seamlessly binds the local project `venv` folder to the physical environment on `E:`:
```cmd
D:\Projects\CodAlpha Task 3\AI-Music-Studio\venv  <=== [JUNCTION] ===>  E:\banka\Development\VirtualEnvironments\ai_music_studio_venv
```

---

## 🔧 Windows C++ Runtime & TensorFlow Fix

TensorFlow 2.21.0 on Windows requires Microsoft Visual C++ 2015–2022 redistributable runtimes (`msvcp140.dll`, `msvcp140_1.dll`, and `vcruntime140_threads.dll`).

1. The verified 64-bit runtime libraries were downloaded to `E:\banka\Development\Tools\vcredist_dlls\`.
2. Deployed DLLs into:
   - `venv\Scripts\`
   - `venv\Lib\site-packages\tensorflow\`
   - `C:\Users\banka\AppData\Local\Programs\Python\Python311\`
3. TensorFlow's `__init__.py` has been configured with `os.add_dll_directory` to ensure standard dynamic link loading on Windows.

---

## 🚀 How to Run the Project

### Option A: Using Helper Launch Scripts (One-Click)

From the project root (`D:\Projects\CodAlpha Task 3\AI-Music-Studio`):

- To run the **Backend**: Double-click or execute `run_backend.bat`
- To run the **Frontend**: Double-click or execute `run_frontend.bat`
- To launch **Both** concurrently: Double-click or execute `start.bat`

---

### Option B: Using VS Code Integrated Terminals (Recommended)

#### Terminal 1 — Backend (FastAPI + Uvicorn)
```powershell
cd "D:\Projects\CodAlpha Task 3\AI-Music-Studio"
.\venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```
- **API URL:** http://127.0.0.1:8000
- **Interactive Swagger Docs:** http://127.0.0.1:8000/docs
- **Health Check:** http://127.0.0.1:8000/health

#### Terminal 2 — Frontend (React + Vite)
```powershell
cd "D:\Projects\CodAlpha Task 3\AI-Music-Studio\frontend"
npm run dev
```
- **Web Application URL:** http://localhost:5173

---

## 🧪 Verification & Test Suite

### 1. Backend Automated Tests (Pytest)
```powershell
cd "D:\Projects\CodAlpha Task 3\AI-Music-Studio"
.\venv\Scripts\python.exe -m pytest tests/ -v
```
**Results:** `98 passed, 1 skipped (no local maestro raw file), 0 failed` in ~20s.

Covers:
- `tests/test_health.py`: Health endpoint status and components.
- `tests/test_auth.py`: JWT tokens, password hashing, and user isolation.
- `tests/test_database.py`: CRUD, history, and persistence of generations.
- `tests/test_generator.py`: Autoregressive LSTM token generation, reproducibility, zero UNK token guarantee.
- `tests/test_model.py`: Neural architecture, forward pass, and checkpoint serialization.
- `tests/test_music_representation.py`: Bidirectional MIDI tokenization and roundtrips.
- `tests/test_admin_dashboard.py`: Admin dashboard intelligence metrics and RBAC.
- `tests/test_security.py`: HTTP headers, SQL injection resistance, rate limiting, and path traversal defense.
- `tests/test_train.py`: Chunk dataset batching and training artifact integrity.

### 2. Frontend Automated Tests (Vitest)
```powershell
cd "D:\Projects\CodAlpha Task 3\AI-Music-Studio\frontend"
npm test -- --run
```
**Results:** `12 passed (12)`, 100% test pass rate.

### 3. Frontend Production Build
```powershell
cd "D:\Projects\CodAlpha Task 3\AI-Music-Studio\frontend"
npm run build
```
**Result:** Bundle built cleanly in `< 1.0s` into `frontend/dist/`.

---

## 🎹 Model & Music Generation Pipeline

1. **Vocabulary:** Loaded from `models/lstm/v1/vocabulary.json` and `dataset/processed/vocabulary.json` (36,700 tokens derived from MAESTRO).
2. **Model Architecture:** 2-layer sequential LSTM (`AI_Music_Studio_LSTM`) with 15,049,052 parameters.
3. **Artifact Storage:** Serialized in `models/lstm/v1/model.keras` and `best_model.keras`.
4. **Music Output:** Generated compositions are written to `output/midi/` (`.mid`) and synthesized to `output/audio/` (`.wav`), streamed directly to the frontend player with full HTTP byte range support.
