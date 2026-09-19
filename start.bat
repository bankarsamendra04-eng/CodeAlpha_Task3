@echo off
title AI Music Studio - Launcher
echo ===================================================
echo       Launching AI Music Studio Full Stack
echo ===================================================
echo.
echo Starting Backend API Server (Port 8000)...
start "AI Music Studio Backend" cmd /k "%~dp0run_backend.bat"

echo Starting Frontend Web Client (Port 5173)...
start "AI Music Studio Frontend" cmd /k "%~dp0run_frontend.bat"

echo.
echo ===================================================
echo Both services are starting in separate windows:
echo - Backend API:  http://127.0.0.1:8000
echo - Swagger Docs: http://127.0.0.1:8000/docs
echo - Frontend UI:  http://localhost:5173
echo ===================================================
