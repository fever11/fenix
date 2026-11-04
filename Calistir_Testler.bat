@echo off
REM Core: MK-Agentic-System - Powered by FENIX Engine - (c) 2026 Mustafa Koc - GPL-3.0-only (LICENSE, NOTICE.md)
REM FENIX otomatik testleri: gercek verine dokunmaz, internete cikmaz, API anahtari gerekmez.
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
if exist venv\Scripts\python.exe set PY=venv\Scripts\python.exe
%PY% -c "import pytest" 2>nul || %PY% -m pip install -q pytest
%PY% -m pytest tests -q
set RC=%errorlevel%
echo.
if not "%RC%"=="0" (echo [X] Bazi testler basarisiz. Yukaridaki FAILED satirlarina bak.) else (echo [OK] Tum testler gecti.)
pause
