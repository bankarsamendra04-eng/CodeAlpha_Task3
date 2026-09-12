# Running AI Music Studio from Visual Studio Code Integrated Terminal

This guide provides exact, verified commands specifically tailored for the **integrated terminal in Visual Studio Code on Windows**.

---

## 🔍 Pre-Flight System Audit (Your Project Status)

Before starting the servers, here is the verified status of your local codebase:

| Component | Status | Location / Details |
| :--- | :---: | :--- |
| **Python Virtual Environment** | ✅ Exists | `venv\` (`venv\Scripts\Activate.ps1`, Python 3.11) |
| **Backend Entry Point** | ✅ Verified | `backend/main.py` (`backend.main:app` running on Uvicorn) |
| **Trained LSTM Model** | ✅ Ready | `models/lstm/v1/best_model.keras` (180.6 MB, 15.05M parameters) |
| **Dataset Preprocessing** | ✅ Completed | `dataset/processed/vocabulary.json` & `training_data\` are ready |
| **Raw MAESTRO Dataset** | 🔒 Cached | Configured in `dataset/` — **no re-downloading required** |
| **Groq NLU Engine** | ⚡ Optional | Configured in `.env`; automatic deterministic fallback operates if offline |
| **Frontend Runtime** | ✅ Ready | `frontend/package.json` (`vite` dev server on port 5173) |

> [!NOTE]
> **No training will be initiated.** The model is already trained and will be loaded in inference mode.  
> **No raw datasets will be re-downloaded.**

---

## 🖥️ Two-Terminal VS Code Workflow

In Visual Studio Code, open the integrated terminal (`Ctrl + \`` or menu **Terminal → New Terminal**).

```
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│        TERMINAL 1: BACKEND           │  │        TERMINAL 2: FRONTEND          │
│   FastAPI Server (Port 8000)         │  │   Vite Dev Server (Port 5173)        │
│   Folder: AI-Music-Studio (Root)     │  │   Folder: AI-Music-Studio/frontend   │
└──────────────────────────────────────┘  └──────────────────────────────────────┘
```

---

### TERMINAL 1: FastAPI Backend Service

1. Open your first terminal in VS Code (ensure you are at the project root: `AI-Music-Studio`).
2. Run the following commands in order:

```powershell
# 1. Activate the Python virtual environment
.\venv\Scripts\Activate.ps1

# (Optional: Only if you have not installed requirements or updated packages)
# pip install -r requirements.txt

# 2. Start the FastAPI backend server with hot-reload
uvicorn backend.main:app --reload --port 8000
```

> **Expected Terminal Output:**
> ```text
> INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
> INFO:     Started reloader process [...]
> INFO:     Started server process [...]
> INFO:     Waiting for application startup.
> INFO:     Application startup complete.
> ```

- **Backend Base URL**: [`http://127.0.0.1:8000`](http://127.0.0.1:8000)
- **Interactive API Documentation (Swagger UI)**: [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs)
- **Alternative API Docs (ReDoc)**: [`http://127.0.0.1:8000/redoc`](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [`http://127.0.0.1:8000/health`](http://127.0.0.1:8000/health)

---

### TERMINAL 2: React + Vite Frontend Web UI

1. Open a **second** terminal tab in VS Code:
   - Click the **`+`** (New Terminal) icon or the split-terminal icon in the top right of the terminal panel.
2. Run the following commands:

```powershell
# 1. Navigate into the frontend folder
cd frontend

# (Optional: Only if node_modules is missing or package.json was modified)
# npm install

# 2. Launch the Vite development web server
npm run dev
```

> **Expected Terminal Output:**
> ```text
>   VITE v5.2.0  ready in 320 ms
> 
>   ➜  Local:   http://localhost:5173/
>   ➜  Network: http://192.168.x.x:5173/
>   ➜  press h + enter to show help
> ```

- **Frontend Studio Application URL**: [`http://localhost:5173`](http://localhost:5173)

---

## 🔎 Verification Steps

### 1. Check if the Backend is Running
Open a browser tab or run this command in a new terminal:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```
**Expected JSON Response:**
```json
{
  "status": "healthy",
  "service": "AI Music Studio Backend",
  "groq_service": "available",
  "database": "ok",
  "model_version": "lstm_v1"
}
```

### 2. Check if the Frontend is Connected to the Backend
1. Open [`http://localhost:5173`](http://localhost:5173) in your browser.
2. Look at the top-right corner of the navigation bar:
   - You should see a green dot with the text: **`Backend & DB Online`**.
   - If it displays a red dot with `"Backend Offline"`, check that Terminal 1 is active on port 8000.

---

## 🛑 How to Stop Both Servers

- Click inside **Terminal 1** and press **`Ctrl + C`**. When prompted `Terminate batch job (Y/N)?`, type `Y` and press Enter.
- Click inside **Terminal 2** and press **`Ctrl + C`**. When prompted `Terminate batch job (Y/N)?`, type `Y` and press Enter.

---

## 🛠️ Troubleshooting Common Windows & VS Code Issues

### Issue 1: PowerShell Execution Policy Error
**Symptom:**
```text
File ...\venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled on this system.
```
**Solution:**
Allow script execution for your user account:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
*Or, bypass execution policy for this terminal session:*
```powershell
powershell -ExecutionPolicy Bypass -File .\venv\Scripts\Activate.ps1
```

---

### Issue 2: Port 8000 Already in Use
**Symptom:**
```text
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): only one usage of each socket address is normally permitted
```
**Solution (Find and stop the zombie process occupying port 8000):**
```powershell
# Find process using port 8000 and terminate it
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
```
*Or launch Uvicorn on an alternate port:*
```powershell
uvicorn backend.main:app --reload --port 8001
```

---

### Issue 3: Port 5173 Already in Use (Frontend)
**Symptom:**
Vite automatically switches to port 5174 (`http://localhost:5174`).
**Solution:**
Kill the process using port 5173:
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 5173).OwningProcess | Stop-Process -Force
```

---

### Issue 4: Missing Python Packages
**Symptom:**
```text
ModuleNotFoundError: No module named 'fastapi' (or 'tensorflow', 'music21')
```
**Solution:**
Ensure your virtual environment is active (your terminal prompt must display `(venv)`):
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

### Issue 5: Missing `.env` File
**Symptom:**
Backend reports default fallback credentials or warning about missing `.env`.
**Solution:**
Copy the template file to `.env`:
```powershell
Copy-Item .env.example .env
```

---

### Issue 6: Model Location Verification
**Symptom:**
Backend warns `AI Music Generation Model is unavailable`.
**Solution:**
The model is located at `models/lstm/v1/best_model.keras`. Ensure your working directory is the repository root (`AI-Music-Studio`) when running `uvicorn`. The application automatically finds the model relative to the root.

---

### Issue 7: Dataset Path Warnings
**Symptom:**
Warning regarding raw dataset directory path in logs.
**Solution:**
The dataset has already been preprocessed into `dataset/processed/` and `dataset/dataset_summary.json`. The web studio and music generation endpoints do **not** require the raw MAESTRO directory to generate music.
