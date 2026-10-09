@echo off
title FocusPilot Launcher
cd /d "%~dp0"

echo [FocusPilot] Verificare mediu Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [EROARE] Python nu a fost gasit in PATH.
    pause
    exit /b 1
)

echo [FocusPilot] Pornire aplicatie in mod rezident (System Tray)...
start "" pythonw.exe "%~dp0FocusPilot.pyw"
exit
