# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Sağ tık menüsü ve seçili metin kısayolu (v1.4, Mustafa'nın fikri).

1) Windows Gezgini sağ tık menüsü: dosyaya ya da klasöre sağ tıklayınca "FENIX" alt menüsü çıkar:
     Özetle · Çevir · Bu dosya güvenli mi? · PDF'e dönüştür · FENIX'e sor…
   Seçilen istek yan sohbet (Nöbet) penceresine gider; pencere kapalıysa açılır. Ana pencerenin açılmasını beklemek
   gerekmez. Menü sadece bu kullanıcı için (HKCU) eklenir, yönetici izni istemez ve tek tıkla kaldırılır.
   Windows 11'de klasik menüdedir: "Daha fazla seçenek göster" (Shift+F10) altında görünür.

2) Seçili metin kısayolu: herhangi bir uygulamada metni seç, sayı tuş takımındaki "+" tuşuna BASILI TUT (~0,5 sn).
   Kısa basış eskisi gibi "+" yazar. Seçili metin yan sohbete gelir; "bununla ne yapayım?" diye sorulur (boş bırakıp
   Enter = açıkla).

İstekler data/yan_istek/ klasörüne birer küçük JSON dosyası olarak yazılır; yan sohbet bunları sırayla işler.
"""
import json
import os
import sys
import threading
import time
import uuid

DATA_DIR = "data"
ISTEK_DIR = os.path.join(DATA_DIR, "yan_istek")
KOK = r"Software\Classes"
MENU_ADI = "FENIX"

# eylem: (menü yazısı, istek metni şablonu, doğrudan gönderilsin mi)
EYLEMLER = {
    "ozetle": ("Özetle", "Şu dosyayı oku ve kısaca özetle: {yol}", True),
    "cevir": ("Çevir", "Şu dosyayı oku; Türkçe değilse Türkçeye, Türkçeyse İngilizceye çevir: {yol}", True),
    "guvenli": ("Bu dosya güvenli mi?", None, True),          # yapay zekâ kullanmadan Nöbet denetimiyle
    "pdf": ("PDF'e dönüştür", "Şu dosyanın içeriğini PDF olarak aynı klasöre kaydet (adı aynı, uzantısı .pdf): {yol}",
            True),
    "sor": ("FENIX'e sor…", None, False),                     # yol eklenir, soruyu kullanıcı yazar
}
KLASOR_EYLEMLERI = ["ozetle", "sor"]
DOSYA_EYLEMLERI = ["ozetle", "cevir", "guvenli", "pdf", "sor"]
KLASOR_SABLON = {"ozetle": "Şu klasörde neler var, kısaca özetle: {yol}"}


# ------------------------------------------------------------------ istek kuyruğu (dosya tabanlı, işlemler arası)
def istek_yaz(eylem, yol=None, metin=None):
    os.makedirs(ISTEK_DIR, exist_ok=True)
    kayit = {"eylem": eylem, "yol": yol or "", "metin": metin or "", "zaman": time.time()}
    ad = f"{time.time():.6f}_{uuid.uuid4().hex[:6]}.json"
    gecici = os.path.join(ISTEK_DIR, ad + ".tmp")
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(kayit, f, ensure_ascii=False)
    os.replace(gecici, os.path.join(ISTEK_DIR, ad))       # yarım yazılmış dosya okunmasın
    return kayit


def istekleri_al(en_eski_sn=600):
    """Bekleyen istekleri sırayla döner ve siler. 10 dakikadan eski istekler atılır."""
    try:
        adlar = sorted(a for a in os.listdir(ISTEK_DIR) if a.endswith(".json"))
    except FileNotFoundError:
        return []
    out = []
    for ad in adlar:
        yol = os.path.join(ISTEK_DIR, ad)
        try:
            with open(yol, encoding="utf-8") as f:
                k = json.load(f)
        except Exception:
            k = None
        try:
            os.remove(yol)
        except OSError:
            pass
        if isinstance(k, dict) and time.time() - float(k.get("zaman", 0)) <= en_eski_sn:
            out.append(k)
    return out


def istek_metni(k):
    """İstek -> (gönderilecek metin ya da None, ek bağlam ya da None, kullanıcıya gösterilecek not)."""
    eylem, yol, metin = k.get("eylem"), k.get("yol") or "", k.get("metin") or ""
    if eylem == "metin":
        kisa = " ".join(metin.split())
        return None, metin, f"Seçili metin geldi: “{kisa[:120]}{'…' if len(kisa) > 120 else ''}”"
    if eylem == "sor":
        return None, yol, f"Dosya: {yol}"
    klasor = os.path.isdir(yol)
    sablon = (KLASOR_SABLON.get(eylem) if klasor else None) or (EYLEMLER.get(eylem) or (None, None))[1]
    if not sablon:
        return None, None, ""
    return sablon.format(yol=yol), None, ""


def guvenlik_raporu(yol):
    """'Bu dosya güvenli mi?' — yapay zekâ ve kota kullanmadan Nöbet'in indirme denetimiyle."""
    if not os.path.isfile(yol):
        return f"'{yol}' bir dosya değil ya da bulunamadı."
    try:
        from . import nobet
        r = nobet.classify_download(yol)
    except Exception as e:
        return f"Dosyayı denetleyemedim: {e}"
    seviye = {"kritik": "TEHLİKELİ görünüyor", "dikkat": "dikkat gerektiriyor", "temiz": "bir sorun görünmüyor"}
    sev = r.get("seviye", "temiz")
    satirlar = [f"• {b}" for b in (r.get("notlar") or [])][:8]
    defender = {"temiz": "Windows Defender taramasında tehdit bulunmadı.",
                "tehdit": "Windows Defender bu dosyada TEHDİT buldu."}.get(r.get("defender"), "")
    return (f"{r.get('ad', os.path.basename(yol))}: {seviye.get(sev, sev)}."
            + ("\n" + "\n".join(satirlar) if satirlar else "") + (f"\n{defender}" if defender else "")
            + "\n\nBu denetim dosyanın adına, türüne, imzasına ve Windows Defender'a bakar; içeriğini açmaz ve %100 "
              "garanti değildir.")


# ------------------------------------------------------------------ kayıt defteri (HKCU, yönetici izni gerekmez)
def _komut(eylem):
    """Menü tıklanınca çalışacak komut: pencere açmadan nobet_main --sor <eylem> "<yol>"."""
    from .nobet import python_exe, project_dir
    return f'"{python_exe()}" "{os.path.join(project_dir(), "nobet_main.py")}" --sor {eylem} "%1"'


def anahtarlar():
    """Eklenecek anahtarlar: [(alt anahtar yolu, {değer adı: değer})]. Test edilebilsin diye ayrı."""
    from .nobet import project_dir
    ikon = os.path.join(project_dir(), "fenix.ico")
    out = []
    for hedef, eylemler in (("*", DOSYA_EYLEMLERI), ("Directory", KLASOR_EYLEMLERI)):
        ana = rf"{KOK}\{hedef}\shell\{MENU_ADI}"
        out.append((ana, {"MUIVerb": "FENIX", "SubCommands": "", "Icon": ikon}))
        for i, e in enumerate(eylemler):
            alt = rf"{ana}\shell\{i:02d}_{e}"
            out.append((alt, {"": EYLEMLER[e][0]}))
            out.append((alt + r"\command", {"": _komut(e)}))
    return out


def kurulu_mu():
    if os.name != "nt":
        return False
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{KOK}\*\shell\{MENU_ADI}"))
        return True
    except OSError:
        return False


def kur():
    if os.name != "nt":
        return {"status": "error", "message": "Sağ tık menüsü sadece Windows'ta var."}
    import winreg
    kaldir()                                  # eski sürümün kalıntısı kalmasın
    for yol, degerler in anahtarlar():
        k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, yol)
        for ad, deger in degerler.items():
            winreg.SetValueEx(k, ad, 0, winreg.REG_SZ, deger)
        winreg.CloseKey(k)
    return {"status": "ok", "message": "Sağ tık menüsüne FENIX eklendi (Windows 11'de: Daha fazla seçenek göster)."}


def _sil_agac(winreg, kok, yol):
    try:
        k = winreg.OpenKey(kok, yol, 0, winreg.KEY_ALL_ACCESS)
    except OSError:
        return
    while True:
        try:
            alt = winreg.EnumKey(k, 0)
        except OSError:
            break
        _sil_agac(winreg, kok, yol + "\\" + alt)
    winreg.CloseKey(k)
    try:
        winreg.DeleteKey(kok, yol)
    except OSError:
        pass


def kaldir():
    if os.name != "nt":
        return {"status": "ok", "message": ""}
    import winreg
    for hedef in ("*", "Directory"):
        _sil_agac(winreg, winreg.HKEY_CURRENT_USER, rf"{KOK}\{hedef}\shell\{MENU_ADI}")
    return {"status": "ok", "message": "Sağ tık menüsünden FENIX kaldırıldı."}


# ------------------------------------------------------------------ Numpad "+" basılı tutma
UZUN_BASIS_SN = 0.5
NUMPAD_ARTI = 78          # sayı tuş takımı "+" tuşunun tarama kodu


def secili_metni_al(bekle=0.6):
    """Seçili metni Ctrl+C ile alır, panonun eski metnini geri koyar. Pano değişmezse (seçim yok) ''."""
    try:
        import keyboard
        from .nobet import _read_clipboard, _clipboard_seq
    except Exception:
        return ""
    eski, sira = _read_clipboard() or "", _clipboard_seq()
    keyboard.send("ctrl+c")
    bitis = time.time() + bekle
    while time.time() < bitis and _clipboard_seq() == sira:
        time.sleep(0.03)
    if _clipboard_seq() == sira:
        return ""                                         # hiçbir şey seçili değildi
    time.sleep(0.05)
    yeni = _read_clipboard() or ""
    if eski:
        _pano_yaz(eski)
    return yeni.strip()


def _pano_yaz(metin):
    """Panoya metin yazar (Windows API; ayrı pencere açmaz)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        k32.GlobalAlloc.restype = ctypes.c_void_p
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        veri = metin.encode("utf-16-le") + b"\x00\x00"
        h = k32.GlobalAlloc(0x0002, len(veri))
        p = k32.GlobalLock(h)
        ctypes.memmove(p, veri, len(veri))
        k32.GlobalUnlock(h)
        for _ in range(5):
            if u32.OpenClipboard(0):
                break
            time.sleep(0.05)
        else:
            return
        try:
            u32.EmptyClipboard()
            u32.SetClipboardData(13, h)
        finally:
            u32.CloseClipboard()
    except Exception:
        pass


class NumpadDinleyici:
    """Sayı tuş takımındaki '+' tuşu: kısa basış '+' yazar, basılı tutmak seçili metni yan sohbete gönderir."""

    def __init__(self, gonder=None, sure=UZUN_BASIS_SN):
        self.gonder = gonder or self._varsayilan_gonder
        self.sure = sure
        self._basildi = None
        self._tetiklendi = False
        self._hook = None
        self._zamanlayici = None

    @staticmethod
    def _varsayilan_gonder(metin):
        istek_yaz("metin", metin=metin)
        from . import nobet
        nobet.open_chat()

    def olay(self, ev):
        """keyboard kancası: True = tuş olayını geçir, False = yut."""
        if getattr(ev, "scan_code", None) != NUMPAD_ARTI:
            return True
        if ev.event_type == "down":
            if self._basildi is None:                    # ilk basış (tuş tekrarları yok sayılır)
                self._basildi = time.time()
                self._tetiklendi = False
                self._zamanlayici = threading.Timer(self.sure, self._uzun_basis)
                self._zamanlayici.daemon = True
                self._zamanlayici.start()
            return False
        # bırakıldı
        if self._zamanlayici:
            self._zamanlayici.cancel()
        kisa = not self._tetiklendi
        self._basildi = None
        if kisa:
            threading.Thread(target=self._arti_yaz, daemon=True).start()
        return False

    @staticmethod
    def _arti_yaz():
        try:
            import keyboard
            keyboard.write("+")                           # tarama kodu 0 ile gönderilir, kanca tekrar yakalamaz
        except Exception:
            pass

    def _uzun_basis(self):
        self._tetiklendi = True
        metin = secili_metni_al()
        if metin:
            try:
                self.gonder(metin)
            except Exception as e:
                _kayit(f"seçili metin gönderilemedi: {type(e).__name__}: {e}")
        else:
            _kayit("uzun basış algılandı ama seçili metin alınamadı (Ctrl+C panoyu değiştirmedi)")

    KILIT = os.path.join(DATA_DIR, "numpad.kilit")

    def baslat(self):
        """Ana pencere ve Nöbet aynı anda açıksa kısayolu sadece biri dinler (yoksa '+' iki kez yazılırdı)."""
        if not _kilit_al(self.KILIT):
            _kayit("Numpad + kısayolunu başka bir FENIX işlemi (ör. Nöbet) dinliyor; bu işlem dinlemiyor")
            return False
        try:
            import keyboard
            self._hook = keyboard.hook_key(NUMPAD_ARTI, self.olay, suppress=True)
            _kayit(f"Numpad + kısayolu dinleniyor (işlem {os.getpid()})")
            return True
        except Exception as e:
            _kayit(f"Numpad + kısayolu başlatılamadı: {type(e).__name__}: {e}")
            _kilit_birak(self.KILIT)
            return False

    def durdur(self):
        try:
            import keyboard
            if self._hook is not None:
                keyboard.unhook(self._hook)
        except Exception:
            pass
        if self._hook is not None:
            _kilit_birak(self.KILIT)
        self._hook = None


def _kayit(metin):
    """Konsola ve data/sag_tik.log'a yazar (FENIX konsolsuz açıldığında da sorunu görebilmek için)."""
    print(f"[SAĞ TIK] {metin}")
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "sag_tik.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + metin + "\n")
    except Exception:
        pass


def _kilit_al(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            pid = int(f.read().strip() or 0)
        if pid and pid != os.getpid():
            import psutil
            if psutil.pid_exists(pid):
                # Windows aynı numarayı başka bir programa verebilir: sadece gerçekten bir FENIX işlemiyse sayılır
                cmd = " ".join(psutil.Process(pid).cmdline()).lower()
                if "app.py" in cmd or "nobet_main" in cmd or "fenix" in cmd:
                    return False
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    return True


def _kilit_birak(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            if int(f.read().strip() or 0) == os.getpid():
                os.remove(yol)
    except Exception:
        pass


def main_sor(argv):
    """nobet_main.py --sor <eylem> <yol>: isteği yazar ve yan sohbeti açar (ağır paket yüklemez)."""
    eylem = argv[0] if argv else "sor"
    yol = argv[1] if len(argv) > 1 else ""
    if eylem not in EYLEMLER:
        eylem = "sor"
    istek_yaz(eylem, yol=os.path.abspath(yol) if yol else "")
    from . import nobet
    nobet.open_chat()


if __name__ == "__main__":
    main_sor(sys.argv[1:])
