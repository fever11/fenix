# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
# FENIX kurulumu / setup — Setup.bat tarafından çalıştırılır / started by Setup.bat
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$Host.UI.RawUI.WindowTitle = "FENIX Setup"

$T = @{
 tr = @{ title="FENIX Kurulumu"; py="Python aranıyor..."; nopy="Python 3.10-3.12 bulunamadı."; askwinget="Python 3.12 otomatik kurulsun mu? (E/H)"; wingetdone="Python kuruldu. Bu pencereyi kapatıp Setup.bat'ı TEKRAR çalıştır."; manual="Python'u https://www.python.org/downloads/ adresinden kur. Kurarken 'Add python.exe to PATH' kutusunu işaretle, sonra Setup.bat'ı tekrar çalıştır."; venv="Sanal ortam hazırlanıyor..."; venvfail="Sanal ortam oluşturulamadı."; pkgs="Paketler kuruluyor (5-10 dakika sürebilir, pencereyi kapatma)..."; pkgfail="Bazı paketler kurulamadı. Yukarıdaki hatayı ve docs\INSTALL_TR.md rehberini kontrol et."; short="Masaüstüne FENIX kısayolu eklendi."; done="Kurulum tamamlandı!"; key="FENIX ilk açılışta API anahtarını soracak: anahtarı pencereye yapıştırman yeterli."; start="FENIX şimdi açılsın mı? (E/H)"; bye="Masaüstündeki FENIX simgesiyle istediğin zaman açabilirsin."; press="Kapatmak için Enter'a bas" }
 en = @{ title="FENIX Setup"; py="Looking for Python..."; nopy="Python 3.10-3.12 was not found."; askwinget="Install Python 3.12 automatically? (Y/N)"; wingetdone="Python installed. Close this window and run Setup.bat AGAIN."; manual="Install Python from https://www.python.org/downloads/. Tick 'Add python.exe to PATH' while installing, then run Setup.bat again."; venv="Preparing the virtual environment..."; venvfail="Could not create the virtual environment."; pkgs="Installing packages (may take 5-10 minutes, don't close the window)..."; pkgfail="Some packages failed to install. Check the error above and docs\INSTALL_EN.md."; short="FENIX shortcut added to the desktop."; done="Setup complete!"; key="On first start FENIX will ask for your API key: just paste it into the window."; start="Start FENIX now? (Y/N)"; bye="You can start FENIX any time from the desktop icon."; press="Press Enter to close" }
 de = @{ title="FENIX-Installation"; py="Python wird gesucht..."; nopy="Python 3.10-3.12 wurde nicht gefunden."; askwinget="Python 3.12 automatisch installieren? (J/N)"; wingetdone="Python wurde installiert. Schließe dieses Fenster und starte Setup.bat ERNEUT."; manual="Installiere Python von https://www.python.org/downloads/. Hake 'Add python.exe to PATH' an und starte dann Setup.bat erneut."; venv="Virtuelle Umgebung wird vorbereitet..."; venvfail="Virtuelle Umgebung konnte nicht erstellt werden."; pkgs="Pakete werden installiert (5-10 Minuten, Fenster nicht schließen)..."; pkgfail="Einige Pakete konnten nicht installiert werden. Siehe Fehler oben und docs\INSTALL_DE.md."; short="FENIX-Verknüpfung auf dem Desktop erstellt."; done="Installation abgeschlossen!"; key="Beim ersten Start fragt FENIX nach deinem API-Schlüssel: einfach ins Fenster einfügen."; start="FENIX jetzt starten? (J/N)"; bye="Du kannst FENIX jederzeit über das Desktop-Symbol starten."; press="Enter zum Schließen" }
 ru = @{ title="Установка FENIX"; py="Поиск Python..."; nopy="Python 3.10-3.12 не найден."; askwinget="Установить Python 3.12 автоматически? (Д/Н)"; wingetdone="Python установлен. Закройте это окно и запустите Setup.bat ЕЩЁ РАЗ."; manual="Установите Python с https://www.python.org/downloads/. Отметьте 'Add python.exe to PATH', затем снова запустите Setup.bat."; venv="Подготовка виртуального окружения..."; venvfail="Не удалось создать виртуальное окружение."; pkgs="Установка пакетов (5-10 минут, не закрывайте окно)..."; pkgfail="Некоторые пакеты не установились. Смотрите ошибку выше и docs\INSTALL_RU.md."; short="Ярлык FENIX добавлен на рабочий стол."; done="Установка завершена!"; key="При первом запуске FENIX попросит API-ключ: просто вставьте его в окно."; start="Запустить FENIX сейчас? (Д/Н)"; bye="FENIX можно запустить в любой момент значком на рабочем столе."; press="Нажмите Enter, чтобы закрыть" }
 fr = @{ title="Installation de FENIX"; py="Recherche de Python..."; nopy="Python 3.10-3.12 introuvable."; askwinget="Installer Python 3.12 automatiquement ? (O/N)"; wingetdone="Python est installé. Fermez cette fenêtre et relancez Setup.bat."; manual="Installez Python depuis https://www.python.org/downloads/. Cochez 'Add python.exe to PATH', puis relancez Setup.bat."; venv="Préparation de l'environnement virtuel..."; venvfail="Impossible de créer l'environnement virtuel."; pkgs="Installation des paquets (5-10 minutes, ne fermez pas la fenêtre)..."; pkgfail="Certains paquets n'ont pas pu être installés. Voir l'erreur ci-dessus et docs\INSTALL_FR.md."; short="Raccourci FENIX ajouté au bureau."; done="Installation terminée !"; key="Au premier démarrage, FENIX demandera votre clé API : collez-la simplement dans la fenêtre."; start="Démarrer FENIX maintenant ? (O/N)"; bye="Vous pouvez lancer FENIX à tout moment depuis l'icône du bureau."; press="Appuyez sur Entrée pour fermer" }
 es = @{ title="Instalación de FENIX"; py="Buscando Python..."; nopy="No se encontró Python 3.10-3.12."; askwinget="¿Instalar Python 3.12 automáticamente? (S/N)"; wingetdone="Python instalado. Cierra esta ventana y vuelve a ejecutar Setup.bat."; manual="Instala Python desde https://www.python.org/downloads/. Marca 'Add python.exe to PATH' y vuelve a ejecutar Setup.bat."; venv="Preparando el entorno virtual..."; venvfail="No se pudo crear el entorno virtual."; pkgs="Instalando paquetes (5-10 minutos, no cierres la ventana)..."; pkgfail="Algunos paquetes no se instalaron. Revisa el error de arriba y docs\INSTALL_ES.md."; short="Acceso directo de FENIX añadido al escritorio."; done="¡Instalación completada!"; key="En el primer inicio FENIX te pedirá la clave de API: solo pégala en la ventana."; start="¿Iniciar FENIX ahora? (S/N)"; bye="Puedes iniciar FENIX cuando quieras desde el icono del escritorio."; press="Pulsa Intro para cerrar" }
}

function Yes($a) { return ($a -and ("eEyYjJдДoOsS".Contains($a.Trim().Substring(0,1)))) }

# ---- 1) Dil / language ----
Clear-Host
Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkYellow
Write-Host "     F.E.N.I.X.   Setup" -ForegroundColor Yellow
Write-Host "  =============================================" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "   1) Türkçe     2) English    3) Deutsch"
Write-Host "   4) Русский    5) Français   6) Español"
Write-Host ""
$codes = @("tr","en","de","ru","fr","es")
$sel = Read-Host "  Dil / Language [1-6]"
$i = 0; [int]::TryParse($sel, [ref]$i) | Out-Null
if ($i -lt 1 -or $i -gt 6) { $i = 2 }
$L = $codes[$i-1]; $M = $T[$L]
Write-Host ""; Write-Host "  == $($M.title) ==" -ForegroundColor Yellow; Write-Host ""

# ---- 2) Python ----
Write-Host "  [1/4] $($M.py)"
$py = $null
foreach ($c in @(@("py","-3.12"), @("py","-3.11"), @("py","-3.10"), @("python"))) {
    try {
        $v = & $c[0] $c[1..9] -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v -match '^3\.(10|11|12)$') { $py = $c; break }
    } catch {}
}
if (-not $py) {
    Write-Host "  [X] $($M.nopy)" -ForegroundColor Red
    if ((Get-Command winget -ErrorAction SilentlyContinue) -and (Yes (Read-Host "      $($M.askwinget)"))) {
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        Write-Host ""; Write-Host "  $($M.wingetdone)" -ForegroundColor Yellow
    } else {
        Write-Host "      $($M.manual)" -ForegroundColor Yellow
    }
    Read-Host "  $($M.press)" | Out-Null
    exit 1
}
Write-Host "        Python $v" -ForegroundColor Green

# ---- 3) Sanal ortam + paketler / venv + packages ----
$vpy = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) {
    Write-Host "  [2/4] $($M.venv)"
    & $py[0] $py[1..9] -m venv venv
    if (-not (Test-Path $vpy)) { Write-Host "  [X] $($M.venvfail)" -ForegroundColor Red; Read-Host "  $($M.press)" | Out-Null; exit 1 }
} else { Write-Host "  [2/4] venv OK" }
Write-Host "  [3/4] $($M.pkgs)"
& $vpy -m pip install --upgrade pip --quiet
& $vpy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host ""; Write-Host "  [!] $($M.pkgfail)" -ForegroundColor Red; Read-Host "  $($M.press)" | Out-Null; exit 1 }
# Python dosyalari onceden derlenir: ilk acilis daha hizli / precompile for a faster first start
& $vpy -m compileall -q app.py nobet_main.py modules | Out-Null

# ---- 4) Ayarlar + kısayol / settings + shortcut ----
Write-Host "  [4/4] ..."
if (-not (Test-Path "config.yaml")) { Copy-Item "config.example.yaml" "config.yaml" }
New-Item -ItemType Directory -Force -Path "data" | Out-Null
$st = Join-Path $Root "data\ayarlar.json"
if (-not (Test-Path $st)) { [IO.File]::WriteAllText($st, "{`n  `"language`": `"$L`"`n}") }   # UTF-8, BOM yok
try {
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "FENIX.lnk"))
    $lnk.TargetPath = Join-Path $env:SystemRoot "System32\wscript.exe"
    $lnk.Arguments = '"' + (Join-Path $Root "Start_FENIX.vbs") + '"'
    $lnk.WorkingDirectory = $Root
    $lnk.IconLocation = (Join-Path $Root "fenix.ico")
    $lnk.Save()
    Write-Host "        $($M.short)" -ForegroundColor Green
} catch {}

Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkYellow
Write-Host "   $($M.done)" -ForegroundColor Green
Write-Host "   $($M.key)"
Write-Host "  =============================================" -ForegroundColor DarkYellow
Write-Host ""
if (Yes (Read-Host "  $($M.start)")) {
    Start-Process -FilePath (Join-Path $env:SystemRoot "System32\wscript.exe") -ArgumentList ('"' + (Join-Path $Root "Start_FENIX.vbs") + '"') -WorkingDirectory $Root
} else {
    Write-Host "  $($M.bye)"
    Read-Host "  $($M.press)" | Out-Null
}
