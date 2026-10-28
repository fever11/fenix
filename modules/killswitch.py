# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Acil Kapatma: kısayol tuşu veya fare sol üst köşe.

Köşe tetiği yanlışlıkla çalışmasın diye:
- Fare köşede en az `hold_seconds` (varsayılan 1.5 sn) KESİNTİSİZ beklemeli (geçerken kapanmaz).
- Ekran alıntısı (Win+Shift+S / Ekran Alıntısı Aracı) açıkken köşe tetiği yok sayılır; alıntı seçerken
  fare sık sık sol üst köşeden başlar.
Kullanıcının kendi isteğiyle kapatması (kısayol, köşe, X) kaydedilmez; sadece çökmeler kaydedilir.
"""
import os
import time
import datetime
import threading
import keyboard


def _cursor_pos():
    """Fare konumu. Windows'ta ctypes (hafif); diğerlerinde pyautogui.
    Okunamazsa None (ör. bilgisayar KİLİTLİYKEN Windows konumu vermez; eskiden bu (0,0) = sol üst köşe sanılıp
    FENIX kendini kapatıyordu)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        pt = wintypes.POINT()
        if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            return None
        return pt.x, pt.y
    import pyautogui
    return pyautogui.position()


def _session_locked():
    """Bilgisayar kilitli / ekran koruyucu / oturum geçişi: kullanıcı fareyi kullanmıyor demektir.
    Windows'ta kilitliyken giriş masaüstü açılamaz ve önde pencere olmaz."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hdesk = user32.OpenInputDesktop(0, False, 0x0100)       # DESKTOP_SWITCHDESKTOP
        if not hdesk:
            return True
        try:
            if not user32.SwitchDesktop(hdesk):                  # kilit ekranı açıkken başarısız olur
                return True
        finally:
            user32.CloseDesktop(hdesk)
        return user32.GetForegroundWindow() == 0
    except Exception:
        return False

# Ekran alıntısı / kayıt araçları (pencere başlığı ya da işlem adı)
_SNIP_HINTS = ("snipping", "screenclipping", "ekran alıntısı", "ekran kırpma", "ekran alıntı", "screen snip",
               "sharex", "lightshot", "greenshot", "snagit", "obs64", "gamebar", "xbox game bar")


def _foreground_info():
    """Öndeki pencerenin başlığı ve işlem adı (Windows). Okunamazsa boş döner."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = ""
        try:
            import psutil
            name = psutil.Process(pid.value).name()
        except Exception:
            pass
        return f"{buf.value} {name}".lower()
    except Exception:
        return ""


LOG_MAX_BYTES = 512 * 1024      # hatalar.log en fazla ~512 KB; aşınca en yeni ~128 KB'ı tutulur


def trim_log(path, max_bytes=LOG_MAX_BYTES, keep_bytes=128 * 1024):
    """Log dosyası büyüdüyse sadece son kısmını bırakır (yer kaplamasın)."""
    try:
        if os.path.getsize(path) > max_bytes:
            with open(path, "rb") as f:
                f.seek(-keep_bytes, os.SEEK_END)
                tail = f.read()
            nl = tail.find(b"\n")
            with open(path, "wb") as f:
                f.write(tail[nl + 1:] if nl >= 0 else tail)
    except Exception:
        pass


def log_exit(reason):
    """Sadece beklenmedik kapanışlar (çökmeler) için kullanılır."""
    try:
        os.makedirs("data", exist_ok=True)
        path = os.path.join("data", "hatalar.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {reason}\n")
        trim_log(path)
    except Exception:
        pass


class KillSwitch:
    def __init__(self, hotkey="ctrl+alt+q", corner_trigger=True, corner_size=5, hold_seconds=1.5, light=False,
                 on_quit=None):
        self.light = light          # True: nöbet işlemi (pyautogui yüklenmez, RAM tasarrufu)
        self.on_quit = on_quit      # kapanmadan önce çağrılır (ör. pid dosyasını sil)
        self.hotkey = hotkey
        self.corner_trigger = corner_trigger
        self.corner_size = corner_size
        self.hold_seconds = hold_seconds

    def _quit(self, reason="kısayol"):
        print(f"\n[KILL-SWITCH] Durduruluyor ({reason})...")
        log_exit(f"acil kapatma: {reason}")         # sebebi bilinsin (kendiliğinden kapandı sanılmasın)
        if self.on_quit:
            try:
                self.on_quit()
            except Exception:
                pass
        os._exit(0)

    def _watch_corner(self):
        since = None
        while True:
            try:
                pos = None if _session_locked() else _cursor_pos()
            except Exception:
                pos = None
            if pos is None:                    # kilitli / konum okunamadı: köşe sayılmaz
                since = None
                time.sleep(0.5)
                continue
            x, y = pos
            in_corner = x <= self.corner_size and y <= self.corner_size
            if in_corner and any(h in _foreground_info() for h in _SNIP_HINTS):
                in_corner = False              # ekran alıntısı yapılıyor: yok say
            if in_corner:
                since = since or time.time()
                if time.time() - since >= self.hold_seconds:
                    self._quit(f"fare sol üst köşede {self.hold_seconds} sn bekletildi")
            else:
                since = None
            time.sleep(0.1)

    def start(self):
        if not self.light:
            try:
                import pyautogui
                pyautogui.FAILSAFE = False
            except Exception:
                pass
        try:
            keyboard.add_hotkey(self.hotkey, lambda: self._quit(f"kısayol {self.hotkey}"))
        except Exception as e:
            print(f"[KILL-SWITCH UYARI] Kısayol kaydedilemedi: {e}")
        if self.corner_trigger:
            threading.Thread(target=self._watch_corner, daemon=True).start()
