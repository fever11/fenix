@echo off
REM Core: MK-Agentic-System - Powered by FENIX Engine - (c) 2026 Mustafa Koc - All rights reserved
REM FENIX - Test / debug launcher (console stays open)
chcp 65001 >nul
cd /d "%~dp0"
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe app.py
) else (
    python app.py
)
pause
