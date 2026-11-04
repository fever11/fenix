@echo off
REM Core: MK-Agentic-System - Powered by FENIX Engine - (c) 2026 Mustafa Koc - GPL-3.0-only (LICENSE, NOTICE.md)
REM FENIX eklentileri (MCP): mcp paketi + hazir eklentiler (zaman, git). "dosyalar" eklentisi icin Node.js gerekir.
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
if exist venv\Scripts\python.exe set PY=venv\Scripts\python.exe
echo Eklenti paketleri kuruluyor (FENIX kapali olmali)... Asagida ilerleme gorunur.
%PY% -m pip install -r requirements-mcp.txt
if errorlevel 1 (
    echo [X] Kurulum basarisiz. Yukaridaki hataya bak.
    pause
    exit /b 1
)
echo [OK] mcp, zaman ve git eklentileri kuruldu.
where node >nul 2>nul && (echo [OK] Node.js var: "dosyalar" eklentisi calisir.) || (echo [!] Node.js yok: "dosyalar" eklentisi calismaz. nodejs.org - LTS surumunu kur.)
where git >nul 2>nul && (echo [OK] Git var: "git" eklentisi calisir.) || (echo [!] Git yok: "git" eklentisi calismaz. git-scm.com adresinden kur.)
echo.
echo FENIX'i yeniden ac. Durum: Yetenekler penceresi ya da FENIX'e "hangi eklentiler var?" diye sor.
pause
