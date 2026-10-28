# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
PC Araçları (v5.9.0)
--------------------
Daha önce sadece run_command ile (yapay zekânın her seferinde PowerShell yazmasıyla) yapılabilen işler için
ayrı, test edilmiş, kendi güvenlik kuralı olan araçlar. Ayrı araç olunca komut hafızası bunları yerelde
öğrenip API'ye gitmeden çalıştırabilir.

  delete_file       dosya/klasörü Geri Dönüşüm Kutusu'na taşır (HER SEFERİNDE onay)
  adjust_volume     sesi arttır / azalt / sessize al (set_system_volume sadece 0-100 verir)
  set_brightness    ekran parlaklığı (dizüstü iç ekranı)
  set_radio         Wi-Fi / Bluetooth aç-kapat-durum (Wi-Fi'yi kapatmak onay ister)
  close_app         uygulamayı nazikçe kapatır (zorla kapatma onay ister)
  media_control     oynat/duraklat, sonraki, önceki, durdur
  power_action      ekranı kilitle, uyut (onaylı), ekranı kapat
  window_action     pencereleri listele / küçült / büyüt / öne getir / hepsini küçült
  scan_pc           kurulu uygulamaları, klasörleri, ses cihazlarını vb. tarayıp data/bilgisayar/ altına yazar
  list_installed_apps  envanterden uygulama arar

Her araç {"status": "ok"|"error"|"cancelled", "message": <kullanıcıya söylenecek kısa Türkçe cümle>} döner.
Windows dışında "yalnızca Windows'ta" hatası verir (testler gerçek Windows çağrılarını taklit eder).
"""
import os
import re
import json
import time
import ntpath
import datetime

from . import functions as fx

_INV_PATH = os.path.join("data", "bilgisayar", "envanter.json")
_WIN_ONLY = {"status": "error", "message": "Bu işlem yalnızca Windows'ta yapılabilir."}


def _fold(t):
    """Küçük harf + Türkçe karakterleri ASCII'ye indirir ('Görev Yöneticisi' -> 'gorev yoneticisi')."""
    t = (t or "").replace("İ", "i").replace("I", "ı").lower()
    return t.translate(str.maketrans("çğıöşüâîû", "cgiosuaiu")).strip()


def _words(t):
    return re.sub(r"[^a-z0-9]+", " ", _fold(t)).strip()


# =====================================================================
#  SES: göreli artır/azalt ve sessize alma
# =====================================================================
def _volume_endpoint():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    dev = AudioUtilities.GetSpeakers()
    iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


def _get_volume():
    return int(round(_volume_endpoint().GetMasterVolumeLevelScalar() * 100))


def _set_volume(v):
    _volume_endpoint().SetMasterVolumeLevelScalar(max(0, min(int(v), 100)) / 100, None)


def _get_mute():
    return bool(_volume_endpoint().GetMute())


def _set_mute(m):
    _volume_endpoint().SetMute(1 if m else 0, None)


def adjust_volume(change: int = 0, mute: str = ""):
    """Sesi göreli değiştirir: change +10 = 10 puan arttır, -10 = 10 puan azalt. mute: on | off | toggle.
    Sessizdeyken sesi arttırmak sessizi de kapatır."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    try:
        change = int(change or 0)
    except Exception:
        return {"status": "error", "message": "Ses değişimi bir sayı olmalı."}
    mute = (mute or "").strip().lower()
    if mute and mute not in ("on", "off", "toggle"):
        return {"status": "error", "message": "mute değeri on, off ya da toggle olmalı."}
    try:
        if mute:
            now = _get_mute()
            want = (not now) if mute == "toggle" else (mute == "on")
            _set_mute(want)
            fx._notify("Ses kapatıldı (sessiz)" if want else "Ses açıldı (sessiz kapalı)")
            if not change:
                return {"status": "ok", "message": "Ses kapatıldı." if want else "Sessiz modu kapattım."}
        cur = _get_volume()
        new = max(0, min(100, cur + change))
        if change:
            if _get_mute() and change > 0:
                _set_mute(False)
            _set_volume(new)
            fx._notify(f"Ses: %{cur} → %{new}")
        return {"status": "ok", "message": f"Ses yüzde {new} oldu.", "onceki": cur, "yeni": new}
    except Exception as e:
        fx.report_error("ses ayarı", e)
        return {"status": "error", "message": fx.GENERIC_ERROR}


# =====================================================================
#  EKRAN PARLAKLIĞI
# =====================================================================
def _read_brightness():
    code, out = fx._ps_run("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop "
                           "| Select-Object -First 1).CurrentBrightness")
    if code != 0 or not out.strip().isdigit():
        return None
    return int(out.strip())


def _write_brightness(level):
    ps = ("Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop | "
          f"ForEach-Object {{ [void](Invoke-CimMethod -InputObject $_ -MethodName WmiSetBrightness "
          f"-Arguments @{{Timeout=[uint32]1; Brightness=[byte]{int(level)}}}) }}")
    code, _ = fx._ps_run(ps)
    return code == 0


def set_brightness(level: int = None, change: int = None):
    """Ekran parlaklığını ayarlar. level: 1-100 kesin değer; change: +10 / -10 göreli. Dizüstü iç ekranı içindir;
    harici monitörlerde Windows bu arayüzü vermez."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    if level is None and change is None:
        cur = _read_brightness()
        if cur is None:
            return {"status": "error", "message": _NO_BRIGHTNESS}
        return {"status": "ok", "message": f"Parlaklık yüzde {cur}.", "yeni": cur}
    try:
        cur = _read_brightness()
        if cur is None:
            return {"status": "error", "message": _NO_BRIGHTNESS}
        new = int(level) if level is not None else cur + int(change)
    except Exception:
        return {"status": "error", "message": "Parlaklık bir sayı olmalı."}
    new = max(1, min(100, new))
    if not _write_brightness(new):
        return {"status": "error", "message": _NO_BRIGHTNESS}
    fx._notify(f"Parlaklık: %{cur} → %{new}")
    return {"status": "ok", "message": f"Parlaklık yüzde {new} oldu.", "onceki": cur, "yeni": new}


_NO_BRIGHTNESS = ("Parlaklığı değiştiremedim. Bu ayar dizüstü bilgisayarın kendi ekranında çalışır; harici monitörün "
                  "parlaklığını monitörün düğmelerinden ayarlaman gerekir.")


# =====================================================================
#  Wi-Fi / Bluetooth (Windows Radio API; yönetici yetkisi gerekmez)
# =====================================================================
_RADIO_PS = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op)); [void]$t.Wait(-1); $t.Result }
[void][Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime]
[void][Windows.Devices.Radios.RadioAccessStatus, Windows.System.Devices, ContentType = WindowsRuntime]
[void](Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]))
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$r = $radios | Where-Object { $_.Kind -eq '__KIND__' } | Select-Object -First 1
if (-not $r) { Write-Output '{"found":false}'; exit 0 }
$access = ''
if ('__STATE__' -ne '') { $access = [string](Await ($r.SetStateAsync('__STATE__')) ([Windows.Devices.Radios.RadioAccessStatus])) }
@{ found = $true; state = [string]$r.State; access = $access } | ConvertTo-Json -Compress
"""

_RADIO_NAMES = {"wifi": ("WiFi", "Wi-Fi"), "bluetooth": ("Bluetooth", "Bluetooth")}


def set_radio(kind: str, state: str = "status"):
    """Wi-Fi ya da Bluetooth radyosunu açar/kapatır ya da durumunu söyler. kind: wifi | bluetooth;
    state: on | off | status. Wi-Fi'yi kapatmak internet bağlantısını keser, bu yüzden onay ister."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    k = _words(kind).replace(" ", "")
    k = {"wi-fi": "wifi", "wifi": "wifi", "kablosuz": "wifi", "bt": "bluetooth", "bluetooth": "bluetooth",
         "blutut": "bluetooth"}.get(k, k)
    if k not in _RADIO_NAMES:
        return {"status": "error", "message": "kind wifi ya da bluetooth olmalı."}
    st = (state or "status").strip().lower()
    if st not in ("on", "off", "status"):
        return {"status": "error", "message": "state on, off ya da status olmalı."}
    win_kind, label = _RADIO_NAMES[k]
    if k == "wifi" and st == "off":
        if not fx._confirm("Wi-Fi kapatılacak",
                           "Wi-Fi kapatılsın mı?",
                           "İnternet bağlantın kesilir; FENIX yapay zekâ modellerine ve web'e ulaşamaz. "
                           "Tekrar açmak için 'Wi-Fi'ı aç' demen yeterli (kablolu bağlantın varsa o çalışmaya devam eder)."):
            return {"status": "cancelled", "message": "Wi-Fi'yi kapatmadım."}
    script = _RADIO_PS.replace("__KIND__", win_kind).replace("__STATE__", {"on": "On", "off": "Off"}.get(st, ""))
    data = fx._ps_json(script, timeout=40)
    if not isinstance(data, dict):
        fx.report_error("radyo", f"{label}: PowerShell sonucu okunamadı")
        return {"status": "error", "message": f"{label} durumuna erişemedim. Ayrıntıyı hata notlarına kaydettim."}
    if not data.get("found"):
        return {"status": "error", "message": f"Bu bilgisayarda {label} cihazı bulunamadı."}
    now = str(data.get("state") or "").lower()
    access = str(data.get("access") or "")
    if st != "status" and access and access.lower() not in ("allowed",):
        return {"status": "error",
                "message": (f"Windows {label} değişikliğine izin vermedi ({access}). Ayarlar > Gizlilik > Radyolar "
                            "bölümünden uygulamaların radyoyu kontrol etmesine izin vermen gerekebilir.")}
    if st == "status":
        return {"status": "ok", "message": f"{label} şu an {'açık' if now == 'on' else 'kapalı'}.", "durum": now}
    fx._notify(f"{label}: {'açıldı' if st == 'on' else 'kapatıldı'}")
    return {"status": "ok", "message": f"{label} {'açıldı' if st == 'on' else 'kapatıldı'}.", "durum": now}


# =====================================================================
#  Uygulama kapatma
# =====================================================================
_NEVER_CLOSE = {"explorer.exe", "dwm.exe", "ctfmon.exe", "sihost.exe", "shellexperiencehost.exe",
                "startmenuexperiencehost.exe", "searchhost.exe", "searchapp.exe", "textinputhost.exe",
                "runtimebroker.exe", "applicationframehost.exe", "fontdrvhost.exe", "taskhostw.exe",
                "securityhealthsystray.exe", "msmpeng.exe", "nissrv.exe"}


def _match_processes(query):
    """Sorgu ('chrome', 'spotify', 'visual studio code') ile eşleşen kapatılabilir süreçler: [(pid, ad)]."""
    import psutil
    q = _words(query)
    if len(q) < 3:
        return []
    stems = {q.replace(" ", "")}
    for a in _inventory().get("uygulamalar", []):
        an = _words(a.get("ad", ""))
        if an and (an == q or q in an.split() or an in q) and a.get("exe"):
            stems.add(a["exe"].lower())
    own = {os.getpid(), os.getppid()}
    try:
        own |= {p.pid for p in psutil.Process().parents()}
    except Exception:
        pass
    critical = {n.lower() for n in getattr(fx, "_CRITICAL_NAMES", set())} | _NEVER_CLOSE
    out = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info.get("name") or "")
            low = name.lower()
            if not low or p.info["pid"] in own or low in critical:
                continue
            stem = _words(low[:-4] if low.endswith(".exe") else low).replace(" ", "")
            if any(stem == s or (len(s) >= 4 and s in stem) or (len(stem) >= 4 and stem in s) for s in stems):
                out.append((p.info["pid"], name))
        except Exception:
            continue
    return out[:30]


def _alive(pids):
    import psutil
    return [p for p in pids if psutil.pid_exists(p)]


def _close_windows(pids):
    ids = ",".join(str(int(p)) for p in pids)
    fx._ps_run(f"Get-Process -Id {ids} -ErrorAction SilentlyContinue | ForEach-Object {{ [void]$_.CloseMainWindow() }}",
               timeout=20)


def close_app(app_name: str, force: bool = False):
    """Çalışan bir uygulamayı kapatır. Önce pencereyi nazikçe kapatır (kaydedilmemiş iş varsa uygulama kendisi
    sorar). Kapanmayan arka plan süreçleri için force=true gerekir; zorla kapatma onay kutusu gösterir."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    procs = _match_processes(app_name)
    if not procs:
        return {"status": "error", "message": f"'{app_name}' çalışıyor görünmüyor."}
    names = sorted({n for _, n in procs})
    pids = [p for p, _ in procs]
    if not force:
        fx._notify(f"Uygulama kapatılıyor: {', '.join(names)}")
        _close_windows(pids)
        for _ in range(8):
            time.sleep(0.5)
            if not _alive(pids):
                break
        left = _alive(pids)
        if not left:
            return {"status": "ok", "message": f"{names[0].removesuffix('.exe')} kapatıldı."}
        return {"status": "ok",
                "message": (f"{names[0].removesuffix('.exe')} penceresini kapatmayı denedim ama {len(left)} süreç hâlâ "
                            "çalışıyor (kaydedilmemiş bir iş soruyor ya da arka planda çalışıyor olabilir). Zorla "
                            "kapatmamı istersen söyle."),
                "kalan": len(left)}
    if not fx._confirm("Uygulama zorla kapatılacak",
                       f"{', '.join(n.removesuffix('.exe') for n in names)} zorla kapatılsın mı?",
                       f"{len(procs)} süreç sonlandırılır. Kaydedilmemiş veriler kaybolur."):
        return {"status": "cancelled", "message": "Zorla kapatmadım."}
    import psutil
    done = 0
    for pid in pids:
        try:
            psutil.Process(pid).terminate()
            done += 1
        except Exception:
            pass
    time.sleep(1)
    left = _alive(pids)
    for pid in left:
        try:
            psutil.Process(pid).kill()
        except Exception:
            pass
    return {"status": "ok", "message": f"{names[0].removesuffix('.exe')} zorla kapatıldı."}


# =====================================================================
#  Medya tuşları, kilit, uyku, ekranı kapatma
# =====================================================================
_MEDIA_KEYS = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "stop": 0xB2}
_MEDIA_TR = {"play_pause": "Oynat/duraklat", "next": "Sonraki parça", "previous": "Önceki parça", "stop": "Durduruldu"}


def _press_key(vk):
    import ctypes
    u = ctypes.windll.user32
    u.keybd_event(vk, 0, 0, 0)
    u.keybd_event(vk, 0, 2, 0)


def media_control(action: str):
    """Çalan medyayı kontrol eder (Spotify, YouTube, tarayıcı, VLC...): play_pause | next | previous | stop."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    a = (action or "").strip().lower().replace("-", "_")
    a = {"play": "play_pause", "pause": "play_pause", "toggle": "play_pause", "prev": "previous"}.get(a, a)
    if a not in _MEDIA_KEYS:
        return {"status": "error", "message": "action play_pause, next, previous ya da stop olmalı."}
    try:
        _press_key(_MEDIA_KEYS[a])
    except Exception as e:
        fx.report_error("medya tuşu", e)
        return {"status": "error", "message": fx.GENERIC_ERROR}
    fx._notify(f"Medya: {_MEDIA_TR[a]}")
    return {"status": "ok", "message": _MEDIA_TR[a] + "."}


def _lock():
    import ctypes
    ctypes.windll.user32.LockWorkStation()


def _screen_off():
    import ctypes
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)


def _suspend():
    code, _ = fx._ps_run("Add-Type -AssemblyName System.Windows.Forms; "
                         "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)", timeout=20)
    return code == 0


def power_action(action: str):
    """lock: ekranı kilitler. screen_off: ekranı kapatır (bilgisayar çalışmaya devam eder). sleep: bilgisayarı
    uyutur (onay ister, açık çalışmalar uykuda kalır)."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    a = (action or "").strip().lower().replace("-", "_")
    a = {"kilitle": "lock", "uyku": "sleep", "uyut": "sleep", "ekran_kapat": "screen_off"}.get(a, a)
    if a not in ("lock", "sleep", "screen_off"):
        return {"status": "error", "message": "action lock, sleep ya da screen_off olmalı."}
    try:
        if a == "lock":
            _lock()
            fx._notify("Ekran kilitlendi")
            return {"status": "ok", "message": "Ekranı kilitledim."}
        if a == "screen_off":
            _screen_off()
            fx._notify("Ekran kapatıldı")
            return {"status": "ok", "message": "Ekranı kapattım."}
        if not fx._confirm("Bilgisayar uyutulacak", "Bilgisayar uyku moduna geçsin mi?",
                           "Açık programların durumu korunur; ama FENIX de uykuya geçer. Geri gelmek için bir "
                           "tuşa bas ya da güç düğmesine dokun."):
            return {"status": "cancelled", "message": "Bilgisayarı uyutmadım."}
        if not _suspend():
            return {"status": "error", "message": "Uyku moduna geçemedi (güç ayarları engelliyor olabilir)."}
        return {"status": "ok", "message": "Uyku moduna geçiyor."}
    except Exception as e:
        fx.report_error("güç işlemi", e)
        return {"status": "error", "message": fx.GENERIC_ERROR}


# =====================================================================
#  Pencere yönetimi
# =====================================================================
def _enum_windows():
    """Görünür, başlığı olan üst düzey pencereler: [(hwnd, başlık)]."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    out = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value and buf.value != "Program Manager":
                    out.append((hwnd, buf.value))
        return True
    user32.EnumWindows(proto(cb), 0)
    return out


def _show_window(hwnd, cmd):
    import ctypes
    ctypes.windll.user32.ShowWindow(hwnd, cmd)


def _focus_window(hwnd):
    import ctypes
    u = ctypes.windll.user32
    _show_window(hwnd, 9)            # restore
    u.keybd_event(0x12, 0, 0, 0)     # Alt tuşuna basmak Windows'un ön plana alma kilidini aşar
    u.keybd_event(0x12, 0, 2, 0)
    u.SetForegroundWindow(hwnd)


def _win_hotkey(vk_mod, vk_key, shift=False):
    import ctypes
    u = ctypes.windll.user32
    seq = [vk_mod] + ([0x10] if shift else []) + [vk_key]
    for k in seq:
        u.keybd_event(k, 0, 0, 0)
    for k in reversed(seq):
        u.keybd_event(k, 0, 2, 0)


_SW = {"minimize": 6, "maximize": 3, "restore": 9}
_WIN_TR = {"minimize": "küçültüldü", "maximize": "ekranı kapladı", "restore": "eski boyutuna döndü",
           "focus": "öne getirildi"}


def window_action(action: str, title: str = ""):
    """Pencereleri yönetir. action: list (açık pencereleri say) | minimize_all (hepsini küçült, masaüstünü göster) |
    restore_all (hepsini geri getir) | minimize | maximize | restore | focus (başlığında `title` geçen pencere)."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    a = (action or "").strip().lower().replace("-", "_")
    try:
        if a == "list":
            titles = [t for _, t in _enum_windows()][:40]
            return {"status": "ok", "message": f"{len(titles)} açık pencere var.", "pencereler": titles}
        if a == "minimize_all":
            _win_hotkey(0x5B, 0x4D)
            return {"status": "ok", "message": "Bütün pencereleri küçülttüm."}
        if a == "restore_all":
            _win_hotkey(0x5B, 0x4D, shift=True)
            return {"status": "ok", "message": "Pencereleri geri getirdim."}
        if a in ("minimize", "maximize", "restore", "focus"):
            q = _words(title)
            if not q:
                return {"status": "error", "message": "Hangi pencere? title (başlıkta geçen kelime) vermelisin."}
            hits = [(h, t) for h, t in _enum_windows() if q in _words(t)]
            if not hits:
                return {"status": "error", "message": f"Başlığında '{title}' geçen açık pencere bulamadım."}
            h, t = hits[0]
            if a == "focus":
                _focus_window(h)
            else:
                _show_window(h, _SW[a])
            fx._notify(f"Pencere {_WIN_TR[a]}: {t[:60]}")
            return {"status": "ok", "message": f"{t[:50]} {_WIN_TR[a]}."}
        return {"status": "error", "message": "action list, minimize_all, restore_all, minimize, maximize, restore "
                                              "ya da focus olmalı."}
    except Exception as e:
        fx.report_error("pencere", e)
        return {"status": "error", "message": fx.GENERIC_ERROR}


# =====================================================================
#  Bağlamlı komutlar ve farkındalık (v5.10.1): "bunu kapat", "ne çalışıyor", "bilgisayar neden yavaş"
#  Pencere BAŞLIKLARI okunmaz/saklanmaz; yalnızca program adı ve pencere sırası kullanılır.
# =====================================================================
_SHELL_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW", "NotifyIconOverflowWindow",
                  "TopLevelWindowForOverflowXamlIsland", "XamlExplorerHostIslandWindow", "Windows.UI.Core.CoreWindow"}
_FOLDER_CLASSES = {"CabinetWClass", "ExploreWClass"}          # Dosya Gezgini klasör pencereleri
_FRIENDLY = {"chrome": "Chrome", "msedge": "Edge", "firefox": "Firefox", "code": "VS Code", "explorer": "Dosya Gezgini",
             "winword": "Word", "excel": "Excel", "powerpnt": "PowerPoint", "notepad": "Not Defteri",
             "spotify": "Spotify", "discord": "Discord", "whatsapp": "WhatsApp", "ms-teams": "Teams", "teams": "Teams",
             "steam": "Steam", "applicationframehost": "Windows uygulaması", "msmpeng": "Windows Defender",
             "python": "Python", "pythonw": "Python", "cmd": "Komut İstemi", "windowsterminal": "Terminal",
             "taskmgr": "Görev Yöneticisi", "vlc": "VLC", "obs64": "OBS"}


def _pretty(name):
    stem = (name or "").lower()
    stem = stem[:-4] if stem.endswith(".exe") else stem
    return _FRIENDLY.get(stem) or (stem[:1].upper() + stem[1:] if stem else "?")


def _zorder_windows():
    """Görünür, gizlenmemiş, araç penceresi olmayan üst düzey pencereler, EN ÜSTTEN başlayarak: [(hwnd, pid, sınıf)].
    Başlık yalnızca 'boş mu' diye bakılır; okunmaz."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    out = []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            if not user32.GetWindowTextLengthW(hwnd):
                return True
            ex = user32.GetWindowLongW(hwnd, -20)
            if ex & 0x80 and not ex & 0x40000:            # WS_EX_TOOLWINDOW (APPWINDOW değilse)
                return True
            cloaked = wintypes.DWORD(0)
            try:
                ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
            except Exception:
                pass
            if cloaked.value:                              # başka sanal masaüstündeki / hayalet UWP penceresi
                return True
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            if cls.value in _SHELL_CLASSES:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            out.append((hwnd, pid.value, cls.value))
        except Exception:
            pass
        return True
    user32.EnumWindows(proto(cb), 0)
    return out


def _is_minimized(hwnd):
    import ctypes
    return bool(ctypes.windll.user32.IsIconic(hwnd))


def _proc_name(pid):
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:
        return ""


def _own_pids():
    own = {os.getpid(), os.getppid()}
    try:
        import psutil
        own |= {p.pid for p in psutil.Process().parents()}
    except Exception:
        pass
    return own


def front_app(exclude_pids=()):
    """Kullanıcının 'bu' dediği pencere: pencere sırasında en üstteki, FENIX'in kendisi OLMAYAN pencere.
    (Yan sohbete ya da ana pencereye yazarken öndeki pencere FENIX'tir; 'bunu' ondan önceki uygulamadır.)
    -> {'hwnd','pid','ad','sinif','okunur_ad'} ya da None"""
    skip = _own_pids() | set(exclude_pids or ())
    critical = {n.lower() for n in getattr(fx, "_CRITICAL_NAMES", set())} | _NEVER_CLOSE
    for hwnd, pid, cls in _zorder_windows():
        if pid in skip:
            continue
        name = _proc_name(pid)
        low = name.lower()
        if not low or _is_minimized(hwnd):          # küçültülmüş pencere "öndeki" değildir
            continue
        if low in critical and not (low == "explorer.exe" and cls in _FOLDER_CLASSES):
            continue
        return {"hwnd": hwnd, "pid": pid, "ad": name, "sinif": cls, "okunur_ad": _pretty(name)}
    return None


def _post_close(hwnd):
    import ctypes
    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)          # WM_CLOSE: Alt+F4 gibi, uygulama kaydedilmemiş işi sorar


def _window_exists(hwnd):
    import ctypes
    return bool(ctypes.windll.user32.IsWindow(hwnd))


def close_front_app():
    """'Bunu kapat' / 'öndeki pencereyi kapat': FENIX'in kendisi dışında en öndeki pencereyi Alt+F4 gibi NAZİKÇE kapatır
    (uygulama kaydedilmemiş işi kendisi sorar). Kapanan pencerenin programının adı söylenir (başlığı değil)."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    try:
        target = front_app()
        if not target:
            return {"status": "error", "message": "Kapatılacak bir pencere bulamadım."}
        name = target["okunur_ad"]
        fx._notify(f"Öndeki pencere kapatılıyor: {name}")
        _post_close(target["hwnd"])
        for _ in range(6):
            time.sleep(0.5)
            if not _window_exists(target["hwnd"]):
                return {"status": "ok", "kapanan": name,
                        "message": f"{name} penceresini kapattım. Programın tamamını kapatmamı istersen "
                                   f"'{name.lower()}'u tamamen kapat' de."}
        return {"status": "ok", "kapanan": name,
                "message": (f"{name} penceresine kapat dedim ama hâlâ açık; muhtemelen kaydedilmemiş bir iş soruyor. "
                            "Onun ekranına bakıp karar ver.")}
    except Exception as e:
        fx.report_error("öndeki pencere", e)
        return {"status": "error", "message": fx.GENERIC_ERROR}


def _mb(n):
    return f"{n / 1024:.1f} GB" if n >= 1024 else f"{int(n)} MB"


def _grouped_procs(sample=0.0):
    """Program adına göre toplanmış süreçler: [{'ad','cpu','ram_mb'}] (cpu: toplam işlemciye göre yüzde)."""
    import psutil
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except Exception:
            continue
    if sample:
        time.sleep(sample)
    ncpu = os.cpu_count() or 1
    groups = {}
    for p in procs:
        try:
            name = p.info.get("name") or ""
            if not name or name.lower() in ("system idle process", "idle"):
                continue
            g = groups.setdefault(name.lower(), {"ad": name, "cpu": 0.0, "ram_mb": 0.0, "adet": 0})
            g["cpu"] += p.cpu_percent(None) / ncpu
            g["ram_mb"] += p.memory_info().rss / 1048576
            g["adet"] += 1
        except Exception:
            continue
    return list(groups.values())


def _running_apps():
    """Pencereli (kullanıcının gördüğü) programlar, öndekinden arkadakine: [{'ad','pencere','ram_mb','pid'}]."""
    import psutil
    seen, order = {}, []
    for hwnd, pid, cls in _zorder_windows():
        name = _proc_name(pid)
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen[key] = {"ad": _pretty(name), "pencere": 0, "pids": set()}
            order.append(key)
        seen[key]["pencere"] += 1
        seen[key]["pids"].add(pid)
    out = []
    for key in order:
        g = seen[key]
        ram = 0.0
        for pid in g["pids"]:
            try:
                ram += psutil.Process(pid).memory_info().rss / 1048576
            except Exception:
                pass
        # tarayıcı gibi çok süreçli programların belleği: aynı adlı tüm süreçler
        try:
            ram = sum(p.memory_info().rss for p in psutil.process_iter(["name"])
                      if (p.info.get("name") or "").lower() == key) / 1048576 or ram
        except Exception:
            pass
        out.append({"ad": g["ad"], "pencere": g["pencere"], "ram_mb": round(ram), "ham": key})
    return out


def _system_numbers():
    import psutil
    vm = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
        disk_free = 100 - disk.percent
    except Exception:
        disk_free = None
    try:
        b = psutil.sensors_battery()
        batt = (b.percent, b.power_plugged) if b else None
    except Exception:
        batt = None
    return {"ram_yuzde": vm.percent, "ram_bos_mb": vm.available / 1048576, "disk_bos_yuzde": disk_free, "pil": batt,
            "cpu": psutil.cpu_percent(None)}


def _startup_count():
    try:
        return len(fx._startup_programs())
    except Exception:
        return None


def pc_awareness(kind: str = "running"):
    """Bilgisayarda ne olup bittiğini anlatır. SADECE OKUR, hiçbir şeyi kapatmaz.
    kind=running: açık uygulamalar (öndekinden başlayarak, bellekleriyle). kind=slow: bilgisayar neden yavaş
    (işlemci, bellek, disk, pil, açılış programları) ve ne yapılabileceği."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    k = (kind or "running").strip().lower()
    try:
        if k == "slow":
            return _awareness_slow()
        apps = _running_apps()
        if not apps:
            return {"status": "ok", "message": "Şu an açık bir uygulama penceresi görmüyorum.", "uygulamalar": []}
        front = front_app()
        lines = [f"{a['ad']} ({_mb(a['ram_mb'])})" for a in apps[:12]]
        msg = f"Şu an {len(apps)} uygulama açık: " + ", ".join(lines) + "."
        if front:
            msg += f" En önde: {front['okunur_ad']}."
        return {"status": "ok", "message": msg, "uygulamalar": [{k2: a[k2] for k2 in ("ad", "pencere", "ram_mb")} for a in apps],
                "on_plandaki": front["okunur_ad"] if front else None}
    except Exception as e:
        fx.report_error("farkındalık", e)
        return {"status": "error", "message": fx.GENERIC_ERROR}


def _awareness_slow():
    fx._notify("Bilgisayarın neden yavaşladığına bakılıyor")
    groups = _grouped_procs(sample=0.7)
    sysn = _system_numbers()
    top_cpu = sorted(groups, key=lambda g: -g["cpu"])[:3]
    top_ram = sorted(groups, key=lambda g: -g["ram_mb"])[:3]
    cpu_total = max(sysn.get("cpu") or 0, sum(g["cpu"] for g in groups))
    cpu_total = min(100.0, cpu_total)
    findings, hints = [], []

    def names(lst, key):
        return ", ".join(f"{_pretty(g['ad'])} ({_mb(g['ram_mb'])})" if key == "ram" else
                         f"{_pretty(g['ad'])} (%{int(g['cpu'])})" for g in lst)
    if cpu_total >= 70:
        findings.append(f"İşlemci yoğun (yaklaşık %{int(cpu_total)}); en çok kullananlar: {names([g for g in top_cpu if g['cpu'] >= 3], 'cpu')}.")
        hints.append("Gerekmiyorsa yoğun programı kapatabilirsin ('... kapat' de).")
    if sysn["ram_yuzde"] >= 85:
        findings.append(f"Bellek dolu (%{int(sysn['ram_yuzde'])}, boş {_mb(sysn['ram_bos_mb'])}); en çok kullananlar: {names(top_ram, 'ram')}.")
        hints.append("Kullanmadığın tarayıcı sekmelerini ve programları kapatmak en hızlı rahatlatır.")
    df = sysn.get("disk_bos_yuzde")
    if df is not None and df < 10:
        findings.append(f"Sistem diskinde yalnızca %{int(df)} boş yer var; disk dolunca Windows belirgin yavaşlar.")
        hints.append("İndirilenler ve Geri Dönüşüm Kutusu'nu temizlemek iyi bir başlangıç.")
    if sysn.get("pil") and sysn["pil"][0] <= 20 and not sysn["pil"][1]:
        findings.append(f"Pil %{int(sysn['pil'][0])} ve şarjda değil; Windows güç tasarrufuna geçip bilgisayarı yavaşlatabilir.")
        hints.append("Şarja takmak çoğu zaman yavaşlığı düzeltir.")
    sc = _startup_count()
    if sc is not None and sc > 12:
        findings.append(f"Açılışta {sc} program kendiliğinden başlıyor; bilgisayar açılırken ve ilk dakikalarda yavaşlatır.")
        hints.append("'başlangıç programlarını göster' diyerek gereksizleri birlikte ayıklayabiliriz.")
    if findings:
        msg = " ".join(findings) + " " + " ".join(hints[:2])
    else:
        msg = (f"Belirgin bir sorun görmüyorum: işlemci %{int(cpu_total)}, bellek %{int(sysn['ram_yuzde'])} dolu"
               + (f", sistem diskinde %{int(df)} boş" if df is not None else "") + ". "
               "Bilgisayar uzun süredir açıksa yeniden başlatmak ve tarayıcıda çok sekme olup olmadığına bakmak işe yarar.")
    return {"status": "ok", "message": msg,
            "islemci_yuzde": int(cpu_total), "bellek_yuzde": int(sysn["ram_yuzde"]),
            "en_cok_islemci": [{"ad": _pretty(g["ad"]), "yuzde": int(g["cpu"])} for g in top_cpu],
            "en_cok_bellek": [{"ad": _pretty(g["ad"]), "mb": int(g["ram_mb"])} for g in top_ram]}



# =====================================================================
#  Dosya silme (Geri Dönüşüm Kutusu, her seferinde onay)
# =====================================================================
def _protected_reason(path):
    """Silinmemesi gereken yer mi? Döner: sebep metni ya da ''."""
    p = os.path.abspath(path)
    low = p.lower().rstrip("\\/")
    if len(low) <= 3:
        return "Bir sürücünün kökü silinemez."
    home = os.path.abspath(os.path.expanduser("~")).lower()
    sys_dirs = [os.environ.get(v, "") for v in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")]
    sys_dirs += [r"c:\windows", r"c:\program files", r"c:\program files (x86)", r"c:\programdata"]
    for s in sys_dirs:
        s = (s or "").lower().rstrip("\\/")
        if s and (low == s or low.startswith(s + os.sep) or low.startswith(s + "\\") or low.startswith(s + "/")):
            return "Windows ve program klasörleri silinemez."
    if low == home:
        return "Kullanıcı klasörünün kendisi silinemez."
    for name, dirs in fx._alias_dirs().items():
        for d in dirs:
            if low == os.path.abspath(d).lower().rstrip("\\/"):
                return "Masaüstü, Belgeler gibi ana klasörlerin kendisi silinemez; içindeki bir şeyi seçebilirsin."
    try:
        cwd = os.path.abspath(os.getcwd()).lower()
        if cwd == low or cwd.startswith(low + os.sep) or low.startswith(cwd + os.sep) or low.startswith(cwd + "\\"):
            return "Bu FENIX'in kendi klasörü ya da içindeki dosya; buradan silmiyorum."
    except Exception:
        pass
    return ""


def _resolve_target(path):
    path = (path or "").strip().strip('"')
    if not path:
        return None
    if os.path.isabs(path) or (len(path) > 1 and path[1] == ":"):
        return path if os.path.exists(path) else None
    f = fx.resolve_file(path)
    if f:
        return f
    d = fx.resolve_folders(path)
    return d[0] if d else None


def _recycle(path, is_dir):
    api = "DeleteDirectory" if is_dir else "DeleteFile"
    ps = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
          f"[Microsoft.VisualBasic.FileIO.FileSystem]::{api}({fx._psq(path)}, 'OnlyErrorDialogs', 'SendToRecycleBin')")
    code, _ = fx._ps_run(ps, timeout=60)
    return code == 0


def _dir_stats(path, cap=2000):
    files = size = 0
    for root, _, fs in os.walk(path):
        for f in fs:
            files += 1
            try:
                size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
            if files >= cap:
                return files, size, True
    return files, size, False


def delete_file(path: str, reason: str = ""):
    """Dosya ya da klasörü Geri Dönüşüm Kutusu'na taşır (kalıcı silmez; oradan geri alınabilir). Her seferinde onay
    kutusu gösterilir. Windows/Program Files, sürücü kökleri, Masaüstü-Belgeler gibi ana klasörler ve FENIX'in kendi
    klasörü silinemez. Birden çok dosya için her biri ayrı çağrılır."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    target = _resolve_target(path)
    if not target:
        return {"status": "error", "message": f"'{path}' diye bir dosya ya da klasör bulamadım."}
    target = os.path.abspath(target)
    why = _protected_reason(target)
    if why:
        return {"status": "error", "message": why}
    is_dir = os.path.isdir(target)
    if is_dir:
        n, size, capped = _dir_stats(target)
        info = f"Klasör: içinde {n}{'+' if capped else ''} dosya, {fx._fmt_size(size)}"
    else:
        try:
            info = f"Dosya: {fx._fmt_size(os.path.getsize(target))}"
        except OSError:
            info = "Dosya"
    if not fx._confirm("Geri Dönüşüm Kutusu'na taşınacak", f"'{os.path.basename(target)}' silinsin mi?",
                       f"Yol: {target}\n{info}\nNeden: {reason or 'kullanıcı isteği'}\n\n"
                       "Kalıcı silinmez; Geri Dönüşüm Kutusu'ndan geri alınabilir."):
        return {"status": "cancelled", "message": "Silmedim."}
    if not _recycle(target, is_dir):
        fx.report_error("dosya silme", f"{target}: Geri Dönüşüm Kutusu'na taşınamadı")
        return {"status": "error", "message": "Silemedim; dosya başka bir program tarafından açık olabilir."}
    fx._notify(f"Geri Dönüşüm Kutusu'na taşındı: {target}")
    return {"status": "ok", "message": f"'{os.path.basename(target)}' Geri Dönüşüm Kutusu'na taşındı.", "yol": target}


# =====================================================================
#  Bilgisayar taraması (envanter)
# =====================================================================
_SCAN_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$out = @{}
$out.apps = @(Get-StartApps | ForEach-Object { @{ ad = $_.Name; id = $_.AppID } })
$sh = New-Object -ComObject WScript.Shell
$lnks = @()
foreach ($d in @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs")) {
  if (Test-Path $d) {
    Get-ChildItem $d -Recurse -Filter *.lnk | ForEach-Object {
      try { $t = $sh.CreateShortcut($_.FullName).TargetPath; if ($t -like '*.exe') { $lnks += @{ ad = $_.BaseName; hedef = $t } } } catch {}
    }
  }
}
$out.lnks = $lnks
$out.ses = @(Get-CimInstance Win32_SoundDevice | ForEach-Object { $_.Name })
$out.gpu = @(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name })
$out.yazici = @(Get-Printer | ForEach-Object { $_.Name })
$out | ConvertTo-Json -Depth 4 -Compress
"""


def _top_dirs(folder_alias, limit=80):
    names = []
    for base in fx._alias_dirs().get(folder_alias, []):
        try:
            for n in sorted(os.listdir(base)):
                if os.path.isdir(os.path.join(base, n)) and not n.startswith(".") and n.lower() not in fx._SKIP_DIRS:
                    names.append(n)
        except OSError:
            continue
    return list(dict.fromkeys(names))[:limit]


def _build_inventory(raw):
    """PowerShell çıktısından envanter: uygulamalara (varsa) exe adı eklenir (close_app için)."""
    lnk_map = {}
    for l in fx._as_list(raw.get("lnks")):
        if isinstance(l, dict) and l.get("ad") and l.get("hedef"):
            exe = ntpath.basename(str(l["hedef"]))
            lnk_map[_words(l["ad"])] = exe[:-4].lower() if exe.lower().endswith(".exe") else exe.lower()
    apps, seen = [], set()
    for a in fx._as_list(raw.get("apps")):
        if not isinstance(a, dict) or not a.get("ad"):
            continue
        key = _words(a["ad"])
        if key in seen:
            continue
        seen.add(key)
        exe = lnk_map.get(key, "")
        if not exe:
            for lk, lv in lnk_map.items():
                if lk.startswith(key) or key.startswith(lk):
                    exe = lv
                    break
        apps.append({"ad": str(a["ad"]), "exe": exe})
    apps.sort(key=lambda x: _fold(x["ad"]))
    return {
        "tarih": datetime.datetime.now().isoformat(timespec="seconds"),
        "uygulamalar": apps,
        "klasorler": {"masaustu": _top_dirs("masaustu"), "belgeler": _top_dirs("belgeler"),
                      "indirilenler": _top_dirs("indirilenler")},
        "ses_cihazlari": [str(x) for x in fx._as_list(raw.get("ses")) if x],
        "ekran_kartlari": [str(x) for x in fx._as_list(raw.get("gpu")) if x],
        "yazicilar": [str(x) for x in fx._as_list(raw.get("yazici")) if x],
    }


_INV_CACHE = {"mtime": None, "data": None}


def _inventory():
    """Kayıtlı envanter ({} = hiç taranmamış). Dosya değişmedikçe bellekten gelir."""
    try:
        mt = os.path.getmtime(_INV_PATH)
    except OSError:
        return {}
    if _INV_CACHE["mtime"] != mt:
        _INV_CACHE["data"] = fx._load_json(_INV_PATH, {})
        _INV_CACHE["mtime"] = mt
    return _INV_CACHE["data"] or {}


def inventory_age_days():
    """Envanterin yaşı (gün); hiç yoksa None."""
    inv = _inventory()
    try:
        return (datetime.datetime.now() - datetime.datetime.fromisoformat(inv["tarih"])).total_seconds() / 86400
    except Exception:
        return None


def scan_pc():
    """Bilgisayardaki kurulu uygulamaları, masaüstü/belgeler/indirilenler klasör adlarını, ses cihazlarını, ekran
    kartını ve yazıcıları tarayıp kaydeder. Yeni uygulama kurulunca ya da 'bilgisayarı tara' denince çalıştırılır.
    Sadece adları okur, dosya içeriğine bakmaz."""
    if os.name != "nt":
        return dict(_WIN_ONLY)
    raw = fx._ps_json(_SCAN_PS, timeout=90)
    if not isinstance(raw, dict):
        fx.report_error("bilgisayar taraması", "PowerShell sonucu okunamadı")
        return {"status": "error", "message": "Bilgisayarı tarayamadım. Ayrıntıyı hata notlarına kaydettim."}
    inv = _build_inventory(raw)
    try:
        fx._save_json(_INV_PATH, inv)
        _INV_CACHE["mtime"] = None
    except Exception as e:
        fx.report_error("bilgisayar taraması", e)
        return {"status": "error", "message": fx.GENERIC_ERROR}
    fk = sum(len(v) for v in inv["klasorler"].values())
    return {"status": "ok",
            "message": (f"Bilgisayarı taradım: {len(inv['uygulamalar'])} uygulama, {fk} klasör adı, "
                        f"{len(inv['ses_cihazlari'])} ses cihazı."),
            "uygulama_sayisi": len(inv["uygulamalar"])}


def list_installed_apps(query: str = ""):
    """Taranmış kurulu uygulamalar arasında arar. query boşsa özet ve ilk 40 uygulama. Envanter yoksa önce tarar."""
    inv = _inventory()
    if not inv:
        r = scan_pc()
        if r.get("status") != "ok":
            return r
        inv = _inventory()
    apps = [a["ad"] for a in inv.get("uygulamalar", [])]
    q = _words(query)
    if q:
        apps = [a for a in apps if q in _words(a)]
        if not apps:
            return {"status": "ok", "message": f"'{query}' adında kurulu bir uygulama bulamadım.", "uygulamalar": []}
    return {"status": "ok", "message": f"{len(apps)} uygulama{' bulundu' if q else ' kurulu'}.",
            "uygulamalar": apps[:40], "tarih": inv.get("tarih", "")}


def resolve_app(name):
    """Söylenen uygulama adını envanterdeki gerçek ada çevirir ('spotify' -> 'Spotify', 'gorev yoneticisi' ->
    'Görev Yöneticisi'). Envanter hiç yoksa adı olduğu gibi döner; envanter var ama ad yoksa ''."""
    inv = _inventory()
    apps = inv.get("uygulamalar", [])
    if not apps:
        return name
    q = _words(name)
    if not q:
        return ""
    best = ""
    for a in apps:
        w = _words(a["ad"])
        if w == q:
            return a["ad"]
        if not best and (q in w.split() or w.startswith(q + " ") or (len(q) >= 4 and q in w)):
            best = a["ad"]
        if a.get("exe") and _words(a["exe"]).replace(" ", "") == q.replace(" ", "") and not best:
            best = a["ad"]
    return best


def resolve_folder(name):
    """Masaüstü/Belgeler/İndirilenler altındaki klasör adını envanterden doğrular; envanter yoksa adı döner."""
    inv = _inventory()
    folders = inv.get("klasorler")
    if not folders:
        return name
    q = _words(name)
    for lst in folders.values():
        for f in lst:
            if _words(f) == q:
                return f
    for lst in folders.values():
        for f in lst:
            if q and q in _words(f):
                return f
    return ""


# =====================================================================
#  Kayıt: functions.py'nin araç tablolarına eklenir
# =====================================================================
SCHEMAS = [
    {"name": "delete_file",
     "description": ("Dosya ya da klasörü Geri Dönüşüm Kutusu'na taşır (kalıcı silmez). Kullanıcı 'şu dosyayı sil' "
                     "dediğinde kullan; her seferinde onay kutusu çıkar. run_command ile Remove-Item KULLANMA."),
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Dosya/klasör yolu (ör. 'masaüstü/not.txt')"},
         "reason": {"type": "string", "description": "Neden silindiği (onay kutusunda gösterilir)"}},
         "required": ["path"]}},
    {"name": "adjust_volume",
     "description": ("Bilgisayarın sesini göreli değiştirir ya da sessize alır. 'sesi aç/arttır/yükselt' = change +10, "
                     "'kıs/azalt/düşür' = -10, 'çok' ise ±25; kullanıcı sayı söylerse o kadar (ör. 20 arttır = +20). "
                     "'sustur/sesi kapat' = mute on, 'sesi geri aç/sessizi kaldır' = mute off. Kesin seviye "
                     "(ör. yüzde 40 yap) için set_system_volume kullan."),
     "parameters": {"type": "object", "properties": {
         "change": {"type": "integer", "description": "Yüzde puanı; arttırmak için +, azaltmak için -"},
         "mute": {"type": "string", "enum": ["on", "off", "toggle"]}}}},
    {"name": "set_brightness",
     "description": ("Ekran parlaklığını ayarlar (dizüstü iç ekranı). level: 1-100 kesin değer ('parlaklığı yüzde 70 "
                     "yap'); change: göreli ('biraz kıs' = -10, 'arttır' = +10). İkisi de verilmezse mevcut değeri söyler."),
     "parameters": {"type": "object", "properties": {
         "level": {"type": "integer"}, "change": {"type": "integer"}}}},
    {"name": "set_radio",
     "description": ("Wi-Fi ya da Bluetooth'u açar, kapatır ya da durumunu söyler (kind: wifi | bluetooth; state: on | "
                     "off | status). Wi-Fi'yi kapatmak onay ister çünkü internet kesilir."),
     "parameters": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": ["wifi", "bluetooth"]},
         "state": {"type": "string", "enum": ["on", "off", "status"]}}, "required": ["kind"]}},
    {"name": "close_app",
     "description": ("Çalışan bir uygulamayı kapatır ('Spotify'ı kapat', 'Chrome'u kapat'). Önce pencereyi nazikçe "
                     "kapatır; kapanmazsa kullanıcıya söyle, istiyorsa force=true ile (onay kutusuyla) zorla kapat. "
                     "Şüpheli süreçler için stop_process kullan."),
     "parameters": {"type": "object", "properties": {
         "app_name": {"type": "string", "description": "Uygulama adı"}, "force": {"type": "boolean"}},
         "required": ["app_name"]}},
    {"name": "media_control",
     "description": ("Çalan müzik/video'yu kontrol eder: play_pause (oynat/duraklat/devam), next (sonraki şarkı), "
                     "previous (önceki), stop."),
     "parameters": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["play_pause", "next", "previous", "stop"]}}, "required": ["action"]}},
    {"name": "power_action",
     "description": ("lock: ekranı kilitler; screen_off: ekranı kapatır (bilgisayar çalışır); sleep: bilgisayarı "
                     "uyutur (onay ister). Kapatma/yeniden başlatma bu araçta YOK."),
     "parameters": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["lock", "screen_off", "sleep"]}}, "required": ["action"]}},
    {"name": "window_action",
     "description": ("Pencere yönetimi: list (açık pencereler), minimize_all ('masaüstünü göster', 'hepsini küçült'), "
                     "restore_all, minimize/maximize/restore/focus (title: başlığında geçen kelime, ör. 'chrome', "
                     "'not defteri')."),
     "parameters": {"type": "object", "properties": {
         "action": {"type": "string", "enum": ["list", "minimize_all", "restore_all", "minimize", "maximize",
                                               "restore", "focus"]},
         "title": {"type": "string"}}, "required": ["action"]}},
    {"name": "close_front_app",
     "description": ("'Bunu kapat', 'şunu kapat', 'öndeki pencereyi kapat', 'açık olanı kapat' gibi, uygulama ADI "
                     "VERİLMEDEN söylenen kapatma isteği: FENIX'in kendi penceresi hariç en öndeki pencereyi nazikçe "
                     "(Alt+F4 gibi) kapatır. Kullanıcı bir uygulama adı söylediyse bunu DEĞİL close_app kullan."),
     "parameters": {"type": "object", "properties": {}}},
    {"name": "pc_awareness",
     "description": ("Bilgisayarda ne olup bittiğini anlatır, hiçbir şeyi kapatmaz. kind=running: 'ne çalışıyor', "
                     "'hangi uygulamalar açık', 'şu an ne açık' (öndeki uygulama ve bellek kullanımlarıyla). "
                     "kind=slow: 'bilgisayar yavaşladı', 'neden kasıyor/donuyor' (işlemci, bellek, disk, pil ve açılış "
                     "programlarına bakıp nedenini ve ne yapılabileceğini söyler). Sonucun 'message' alanını aktar."),
     "parameters": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": ["running", "slow"]}}}},
    {"name": "scan_pc",
     "description": ("Bilgisayarı tarar: kurulu uygulamalar, masaüstü/belgeler/indirilenler klasör adları, ses cihazları, "
                     "ekran kartı, yazıcılar (sadece adlar, içerik okunmaz). 'bilgisayarı tara', 'yeni kurduğum "
                     "uygulamaları öğren' denince."),
     "parameters": {"type": "object", "properties": {}}},
    {"name": "list_installed_apps",
     "description": ("Kurulu uygulamalarda arar ya da listeler ('Photoshop kurulu mu', 'hangi tarayıcılar var', "
                     "'kurulu uygulamalarım')."),
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}},
]

TOOLS = {
    "delete_file": delete_file, "adjust_volume": adjust_volume, "set_brightness": set_brightness,
    "set_radio": set_radio, "close_app": close_app, "media_control": media_control, "power_action": power_action,
    "window_action": window_action, "scan_pc": scan_pc, "list_installed_apps": list_installed_apps,
    "close_front_app": close_front_app, "pc_awareness": pc_awareness,
}

# Güvenli modda da verilen (sisteme dokunmayan) araçlar
READONLY = {"scan_pc", "list_installed_apps", "pc_awareness"}


def register():
    """functions.py'nin tablolarına eklenir (birden çok kez çağrılması zararsızdır)."""
    fx.WHITELISTED_FUNCTIONS.update(TOOLS)
    fx.READONLY_FUNCTIONS |= READONLY
    have = {s["name"] for s in fx.FUNCTION_SCHEMAS}
    for s in SCHEMAS:
        if s["name"] not in have:
            fx.FUNCTION_SCHEMAS.append(s)


register()
