@echo off
title VN-Transcribe Dev Server
echo.
echo  ========================================
echo   VN-Transcribe  Web UI  Dev Server
echo  ========================================
echo.

cd /d "%~dp0web"

if not exist node_modules (
    echo [*] Installing dependencies...
    call npm install
    echo.
)

echo [*] Starting Vite dev server...
echo [*] Press Ctrl+C to stop.
echo.
npx vite --open
