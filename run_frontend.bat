@echo off
title AI Music Studio - Frontend Web Client
echo ===================================================
echo   AI Music Studio - Starting React Vite Frontend
echo ===================================================
echo [1/2] Navigating to frontend directory...
cd /d "%~dp0\frontend"

echo [2/2] Launching Vite development server on http://localhost:5173...
npm run dev
pause
