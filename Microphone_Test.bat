@echo off
REM Core: MK-Agentic-System - Powered by FENIX Engine - (c) 2026 Mustafa Koc - GPL-3.0-only (LICENSE, NOTICE.md)
REM FENIX - Mikrofon testi / microphone test (without opening the app)
chcp 65001 >nul
cd /d "%~dp0"
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe microphone_test.py
) else (
    python microphone_test.py
)
pause
