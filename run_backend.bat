@echo off
title AI Music Studio - Backend API Server
echo ===================================================
echo   AI Music Studio - Starting FastAPI Backend Server
echo ===================================================
echo [1/2] Navigating to project root...
cd /d "%~dp0"

echo [2/2] Launching Uvicorn server on http://127.0.0.1:8000...
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
pause
