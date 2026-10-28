@echo off
REM Core: MK-Agentic-System - Powered by FENIX Engine - (c) 2026 Mustafa Koc - All rights reserved
REM FENIX - Kurulum / Setup / Installation / Ustanovka / Instalacion
REM Cok dilli kurulum PowerShell ile calisir / multilingual setup runs in PowerShell.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 pause
