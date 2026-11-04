@echo off
REM Core: MK-Agentic-System - Powered by FENIX Engine - (c) 2026 Mustafa Koc - GPL-3.0-only (LICENSE, NOTICE.md)
REM FENIX - Baglanti testi / connection test (Gemini, Groq, Tavily keys and models)
chcp 65001 >nul
cd /d "%~dp0"
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe connection_test.py
) else (
    python connection_test.py
)
pause
