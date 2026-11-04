# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Nöbet modu (v5.10.0)
--------------------
FENIX penceresi kapalıyken bile bilgisayarı izleyen, küçük ve ayrı bir işlem. Sağ alttaki simgeyle her zaman
görünür; kill-switch (Ctrl+Alt+Q, sol üst köşe) onu da tamamen kapatır.

İzlediği şeyler (başka hiçbir şeye bakmaz; ekran ve mikrofon izlenmez):
  • İndirilenler klasörüne yeni inen dosyalar: çift uzantı hilesi (fatura.pdf.exe), adı belge ama aslında program,
    imzasız program, arşivin içinde çalıştırılabilir dosya, Windows Defender sonucu. Belge/resim içeriği OKUNMAZ;
    yalnızca dosyanın ilk 4 baytı ve arşivde dosya ADLARI okunur.
  • Panoya kopyalanan LİNKLER: şüpheliyse haber verir, normalse sessiz kalır. Düz metin ve şifreler okunmaz,
    saklanmaz. Kripto cüzdan adresi birkaç saniyede başka bir adrese dönüşürse (pano ele geçirme) uyarır.
  • Yeni başlayan programlar (Temp/İndirilenler/Public'ten çalışanlar), uzun süre işlemciyi dolduran program, pil.
  • Açılışta otomatik başlayan programlardaki değişiklikler (v5.7.2 bekçisi).
Hiçbir şey kaydedilmez ya da dışarı gönderilir; bilgi yalnızca bellekte tutulur.

Yan sohbet (v5.10.1): simgeye tıklayınca ya da Ctrl+Alt+J ile açılan küçük YAZILI sohbet penceresi (modules/mini_chat.py).
Ayrı, kısa ömürlü bir işlemdir; kapanınca belleği geri verir.

Uyarı: Windows bildirimi + (ayara göre) sesli. Ses, ayrı kısa ömürlü bir işlemle okunur; böylece nöbet hafif kalır.
"""
import os
import re
import sys
import json
import time
import queue
import zipfile
import datetime
import threading
import subprocess

DATA_DIR = "data"
PID_PATH = os.path.join(DATA_DIR, "nobet.pid")
SETTINGS_PATH = os.path.join(DATA_DIR, "nobet_ayar.json")

DEFAULTS = {
    "etkin": True,                # false: X'e basınca nöbet seçeneği hiç sunulmaz
    "kapanis_tercihi": "sor",     # sor | nobet | kapat
    "uyari_sesi": "onemli",       # onemli | hepsi | sessiz
    "sessiz_saat": "23:00-08:00",  # bu aralıkta sesli uyarı yok (bildirim var); boş = kapalı
    "indirilenler": True,
    "pano": True,
    "surecler": True,
    "baslangic_dakika": 30,       # 0 = kapalı
    "defender_tara": True,        # indirilen çalıştırılabilir dosyaları Windows Defender'a taratır (silmez)
    "uygulama_acikken": True,     # FENIX penceresi açıkken de indirilenler/pano bekçisi çalışsın
    "yan_sohbet": True,           # simgeden / kısayoldan açılan yazılı yan sohbet
    "yan_sohbet_kisayol": "ctrl+alt+j",
    "yan_sohbet_mod": "normal",   # safe (Güvenli) | normal
    "yan_sohbet_sesli": False,    # cevapları sesli oku (kapalıysa ses paketleri hiç yüklenmez)
}
LEVELS = ("onemli", "hepsi", "sessiz")
_ORDER = {"temiz": 0, "dikkat": 1, "kritik": 2}


# ---------------------------------------------------------------- ayarlar
def load_settings(cfg_block=None):
    s = dict(DEFAULTS)
    s.update({k: v for k, v in (cfg_block or {}).items() if k in DEFAULTS})
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            user = json.load(f)
        s.update({k: v for k, v in user.items() if k in DEFAULTS})
    except Exception:
        pass
    if s["uyari_sesi"] not in LEVELS:
        s["uyari_sesi"] = "onemli"
    if s["kapanis_tercihi"] not in ("sor", "nobet", "kapat"):
        s["kapanis_tercihi"] = "sor"
    return s


def save_user_settings(**kw):
    """Tepsi menüsü ve kapanış penceresinden yapılan seçimler data/nobet_ayar.json'a yazılır."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        cur = {}
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                cur = json.load(f)
        except Exception:
            pass
        cur.update({k: v for k, v in kw.items() if k in DEFAULTS})
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def quiet_now(spec, now=None):
    """'23:00-08:00' gibi bir aralıkta mıyız? (gece yarısını geçen aralıklar da çalışır)"""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*", spec or "")
    if not m:
        return False
    a, b = int(m.group(1)) * 60 + int(m.group(2)), int(m.group(3)) * 60 + int(m.group(4))
    now = now or datetime.datetime.now()
    cur = now.hour * 60 + now.minute
    if a == b:
        return False
    return a <= cur < b if a < b else (cur >= a or cur < b)


def should_speak(level, severity, quiet=False):
    """Sesli uyarı kuralı: sessiz/sessiz saat = hayır; 'onemli' = yalnızca kritik; 'hepsi' = kritik + dikkat."""
    if level == "sessiz" or quiet:
        return False
    if severity == "kritik":
        return True
    return severity == "dikkat" and level == "hepsi"


# ---------------------------------------------------------------- indirilen dosya denetimi
_TEMP_EXT = {".crdownload", ".part", ".tmp", ".download", ".opdownload", ".partial", ".!ut", ".aria2"}
_DOC_RE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|txt|rtf|csv|jpe?g|png|gif|bmp|mp3|mp4|mkv|avi|zip|rar)\s*\.(exe|scr|bat|cmd|com|"
                     r"js|jse|vbs|vbe|wsf|ps1|msi|jar|lnk|hta|pif)\s*$", re.I)
_PE_EXT = {".exe", ".dll", ".scr", ".com", ".sys", ".cpl", ".ocx", ".pif", ".efi"}
_RUN_EXT = {".exe", ".msi", ".scr", ".com", ".pif", ".dll"}
_SCRIPT_EXT = {".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".hta", ".jar", ".lnk"}
_DISK_EXT = {".iso", ".img", ".vhd", ".vhdx"}
_SCAN_EXT = _RUN_EXT | _SCRIPT_EXT | _DISK_EXT | {".zip", ".rar", ".7z", ".docm", ".xlsm", ".pptm"}
_MACRO_EXT = {".docm", ".xlsm", ".pptm"}


def default_downloads():
    p = os.path.join(os.path.expanduser("~"), "Downloads")
    return p if os.path.isdir(p) else None


def _header(path, n=4):
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def _zip_report(path):
    """Arşivi AÇMADAN yalnızca dosya adlarına bakar. -> (çalıştırılabilirler, çift uzantılılar, şifreli_mi)"""
    execs, doubles, enc = [], [], False
    try:
        with zipfile.ZipFile(path) as z:
            for i, info in enumerate(z.infolist()):
                if i > 2000:
                    break
                name = info.filename
                if info.flag_bits & 0x1:
                    enc = True
                ext = os.path.splitext(name.lower())[1]
                if _DOC_RE.search(name):
                    doubles.append(name)
                elif ext in _RUN_EXT or ext in _SCRIPT_EXT:
                    execs.append(name)
    except Exception:
        pass
    return execs, doubles, enc


def _defender_exe():
    cands = []
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    cands.append(os.path.join(pf, "Windows Defender", "MpCmdRun.exe"))
    base = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "Microsoft", "Windows Defender", "Platform")
    try:
        for d in sorted(os.listdir(base), reverse=True):
            cands.insert(0, os.path.join(base, d, "MpCmdRun.exe"))
    except OSError:
        pass
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def _defender_scan(path):
    """Dosyayı Windows Defender'a taratır, hiçbir şeyi silmez/karantinaya almaz.
    -> 'temiz' | 'tehdit' | 'yok' (Defender yok / çalışmadı)"""
    if os.name != "nt":
        return "yok"
    exe = _defender_exe()
    if not exe:
        return "yok"
    try:
        r = subprocess.run([exe, "-Scan", "-ScanType", "3", "-File", path, "-DisableRemediation"],
                           capture_output=True, timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {0: "temiz", 2: "tehdit"}.get(r.returncode, "yok")
    except Exception:
        return "yok"


def _signature(path):
    try:
        from . import security as sec
        return sec._signatures([path]).get(path, "Unknown")
    except Exception:
        return "Unknown"


def classify_download(path, defender=True):
    """Yeni inen dosyayı inceler. -> {'ad','seviye': temiz|dikkat|kritik, 'notlar': [...], 'defender': ...}
    Belge/resim içeriği okunmaz; yalnızca ad, ilk 4 bayt, imza, arşiv dosya adları ve Defender sonucu."""
    name = os.path.basename(path)
    low = name.lower()
    ext = os.path.splitext(low)[1]
    notes, level = [], "temiz"

    def add(sev, text):
        nonlocal level
        notes.append(text)
        if _ORDER[sev] > _ORDER[level]:
            level = sev

    if "\u202e" in name:
        add("kritik", "adında gizli bir yön işareti var; uzantıyı ters gösterip kandırmak için kullanılır")
    if _DOC_RE.search(name):
        add("kritik", "adı belge/resim gibi görünüyor ama aslında çalıştırılabilir bir dosya (çift uzantı hilesi)")
    hdr = _header(path)
    if hdr[:2] == b"MZ" and ext not in _PE_EXT:
        add("kritik", f"uzantısı {ext or 'yok'} ama dosya aslında bir program")
    if ext in _RUN_EXT:
        sig = _signature(path)
        if sig == "Unsigned":
            add("dikkat", "imzasız program; kimin yazdığı doğrulanamıyor")
        elif sig == "Unknown":
            add("dikkat", "programın imzası doğrulanamadı")
    elif ext in _SCRIPT_EXT:
        add("dikkat", "komut/betik dosyası; ne yaptığını bilmeden çalıştırma")
    if ext in _DISK_EXT:
        add("dikkat", "disk görüntüsü; içine bakamadım, kaynağını tanımıyorsan açma")
    if ext in _MACRO_EXT:
        add("dikkat", "makro içerebilen Office dosyası; açınca 'makroları etkinleştir' deme")
    if ext == ".zip":
        execs, doubles, enc = _zip_report(path)
        if doubles:
            add("kritik", "arşivin içinde çift uzantılı dosya var: " + ", ".join(doubles[:3]))
        if execs:
            add("dikkat", "arşivin içinde çalıştırılabilir dosya var: " + ", ".join(execs[:3]))
        if enc:
            add("dikkat", "şifreli arşiv; içine bakamadım (zararlılar virüs taramasından kaçmak için bunu sık kullanır)")
    verdict = "yok"
    if defender and (ext in _SCAN_EXT or level != "temiz"):
        verdict = _defender_scan(path)
        if verdict == "tehdit":
            add("kritik", "Windows Defender bu dosyada tehdit buldu")
    return {"ad": name, "seviye": level, "notlar": notes, "defender": verdict}


def download_event(res):
    if res["seviye"] == "temiz":
        return None
    crit = res["seviye"] == "kritik"
    ad = res["ad"]
    text = (f"{ad}: " + "; ".join(res["notlar"]) + ". "
            + ("Çalıştırma, açma; kaynağını tanımıyorsan sil." if crit
               else "Sen bilerek indirdiysen sorun olmayabilir; yine de çalıştırmadan önce kaynağından emin ol."))
    if res["defender"] == "temiz":
        text += " Windows Defender taramasında tehdit bulmadı (bu, güvenli olduğunun kanıtı değil)."
    return {"kaynak": "indirilenler", "seviye": res["seviye"],
            "baslik": "İndirilen dosya tehlikeli görünüyor" if crit else "İndirilen dosyada dikkat edilecek bir şey var",
            "metin": text, "kisa": f"İndirdiğin {ad} dosyasında sorun var: {res['notlar'][0]}."}


class DownloadWatcher:
    """İndirilenler klasörünü izler. İlk bakışta mevcut dosyalar 'eski' sayılır; yalnızca sonradan gelenler denetlenir.
    Dosya boyutu iki bakış arası değişmeyince (indirme bitince) bir kez denetlenir."""

    def __init__(self, folder=None, classify=classify_download, defender=True):
        self.folder = folder or default_downloads()
        self.classify = classify
        self.defender = defender
        self._seen = {}
        self._done = set()
        self._first = True

    def poll(self):
        if not self.folder:
            return []
        try:
            names = os.listdir(self.folder)
        except OSError:
            return []
        events = []
        for name in names:
            path = os.path.join(self.folder, name)
            if path in self._done or os.path.splitext(name.lower())[1] in _TEMP_EXT or name.startswith("~$"):
                continue
            try:
                if not os.path.isfile(path):
                    continue
                st = os.stat(path)
            except OSError:
                continue
            if self._first:
                self._done.add(path)
                continue
            key = (st.st_size, st.st_mtime)
            prev = self._seen.get(path)
            if prev and prev == key and st.st_size > 0:
                self._done.add(path)
                self._seen.pop(path, None)
                try:
                    ev = download_event(self.classify(path, self.defender))
                except Exception:
                    ev = None
                if ev:
                    events.append(ev)
            else:
                self._seen[path] = key
        self._first = False
        return events


# ---------------------------------------------------------------- pano
_URL_RE = re.compile(r"^(https?://\S+|www\.\S+)$", re.I)
_WALLETS = (("eth", re.compile(r"^0x[0-9a-fA-F]{40}$")),
            ("btc", re.compile(r"^(bc1[a-z0-9]{25,60}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")),
            ("trx", re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")))


def clipboard_url(text):
    """Panodaki metin TEK bir link ise onu döndürür, değilse None (düz metne/şifreye dokunulmaz)."""
    t = (text or "").strip()
    if not t or len(t) > 2048 or any(c in t for c in "\r\n\t "):
        return None
    return t if _URL_RE.match(t) else None


def wallet_kind(text):
    t = (text or "").strip()
    if not t or len(t) > 80:
        return None
    for kind, rx in _WALLETS:
        if rx.match(t):
            return kind
    return None


def _short_addr(a):
    return a[:6] + "…" + a[-4:]


def link_event(res):
    """check_link sonucundan uyarı olayı. Şüpheli değilse None (sessiz kalınır)."""
    if not res or res.get("status") != "ok" or not str(res.get("karar", "")).startswith("ŞÜPHELİ"):
        return None
    risks = res.get("riskler") or []
    strong = any(k in " ".join(risks) for k in ("BENZER-İSİM", "alt alanda", "e-Devlet", "alfabe", "'@'"))
    host = re.sub(r"^https?://", "", str(res.get("son_adres", "")))[:60]
    return {"kaynak": "pano", "seviye": "kritik" if strong else "dikkat",
            "baslik": "Kopyaladığın link şüpheli",
            "metin": res.get("ozet") or ("; ".join(risks)),
            "kisa": f"Kopyaladığın link şüpheli görünüyor: {host}. {risks[0] if risks else ''}".strip()}


def _read_clipboard():
    """Windows panosundaki metin (yalnızca değiştiğinde çağrılır). Okunamazsa ''."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        u32.GetClipboardData.restype = ctypes.c_void_p
        k32.GlobalLock.restype = ctypes.c_void_p
        for _ in range(5):
            if u32.OpenClipboard(0):
                break
            time.sleep(0.05)
        else:
            return ""
        try:
            h = u32.GetClipboardData(13)          # CF_UNICODETEXT
            if not h:
                return ""
            p = k32.GlobalLock(ctypes.c_void_p(h))
            if not p:
                return ""
            try:
                return ctypes.wstring_at(p)[:4096]
            finally:
                k32.GlobalUnlock(ctypes.c_void_p(h))
        finally:
            u32.CloseClipboard()
    except Exception:
        return ""


def _clipboard_seq():
    if os.name != "nt":
        return 0
    try:
        import ctypes
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    except Exception:
        return 0


class ClipboardWatcher:
    """Pano değişince: tek bir linkse denetler (şüpheliyse olay), cüzdan adresi hızla değişirse olay.
    Metinler saklanmaz: yalnızca son cüzdan türü/adres ve bakılmış linklerin kısa özeti bellekte durur."""

    def __init__(self, reader=_read_clipboard, seq=_clipboard_seq, checker=None, clock=time.time):
        self.reader, self.seq, self.clock = reader, seq, clock
        self.checker = checker
        self._last_seq = None
        self._checked = []
        self._wallet = None          # (tür, adres, zaman)

    def _check_link(self, url):
        if self.checker:
            return self.checker(url)
        from . import security as sec
        return sec.check_link(url)

    def poll(self):
        s = self.seq()
        if s == self._last_seq:
            return []
        first = self._last_seq is None
        self._last_seq = s
        if first:                      # açılışta panoda zaten duran şeye bakma
            return []
        text = self.reader() or ""
        events = []
        kind = wallet_kind(text)
        now = self.clock()
        if kind:
            prev = self._wallet
            if prev and prev[0] == kind and prev[1] != text.strip() and now - prev[2] <= 15:
                events.append({"kaynak": "pano", "seviye": "kritik", "baslik": "Panodaki cüzdan adresi değişti",
                               "metin": (f"Kopyaladığın {kind.upper()} cüzdan adresi {int(now - prev[2])} saniye içinde "
                                         f"başka bir adrese ({_short_addr(prev[1])} → {_short_addr(text.strip())}) dönüştü. "
                                         "Panoyu ele geçiren zararlılar böyle çalışır. Para göndermeden önce adresi "
                                         "kaynağından tekrar kontrol et."),
                               "kisa": "Kopyaladığın cüzdan adresi kendiliğinden değişti. Para göndermeden önce adresi kontrol et."})
            self._wallet = (kind, text.strip(), now)
            return events
        self._wallet = None
        url = clipboard_url(text)
        if url:
            key = url.lower()
            if key not in self._checked:
                self._checked = (self._checked + [key])[-200:]
                try:
                    ev = link_event(self._check_link(url))
                except Exception:
                    ev = None
                if ev:
                    events.append(ev)
        return events


# ---------------------------------------------------------------- süreçler / pil
_RISKY_DIRS = ("\\appdata\\local\\temp\\", "\\downloads\\", "\\users\\public\\")


class ProcessWatcher:
    """Yeni başlayan riskli yoldan programlar, uzun süre işlemciyi dolduranlar ve düşük pil."""

    def __init__(self, cpu_limit=85.0, cpu_polls=6, procs=None, battery=None, ncpu=None, signer=None):
        self.cpu_limit, self.cpu_polls = cpu_limit, cpu_polls
        self._signer = signer or (lambda exe: _signature(exe))     # geçerli imzalı programlar için uyarılmaz (v5.10.2)
        self._iter = procs
        self._battery = battery
        self._ncpu = ncpu
        self._known = None
        self._alerted = set()
        self._hot = {}
        self._cpu_alerted = {}
        self._batt_alert = False
        self._objs = {}

    def _processes(self):
        if self._iter:
            return self._iter()
        import psutil
        out = []
        for p in psutil.process_iter(["pid", "name", "exe"]):
            try:
                pr = self._objs.setdefault(p.pid, p)
                cpu = pr.cpu_percent(None)
                out.append((p.pid, p.info.get("name") or "", p.info.get("exe") or "", cpu))
            except Exception:
                continue
        self._objs = {pid: o for pid, o in self._objs.items() if pid in {x[0] for x in out}}
        return out

    def _batt(self):
        if self._battery:
            return self._battery()
        try:
            import psutil
            b = psutil.sensors_battery()
            return (b.percent, b.power_plugged) if b else None
        except Exception:
            return None

    def poll(self, now=None):
        now = now or time.time()
        events = []
        procs = self._processes()
        ncpu = self._ncpu or (os.cpu_count() or 1)
        first = self._known is None
        current = {}
        for pid, name, exe, cpu in procs:
            current[pid] = name
            low = (exe or "").lower()
            if not first and pid not in (self._known or {}) and any(d in low for d in _RISKY_DIRS):
                if low not in self._alerted:
                    self._alerted.add(low)
                    try:
                        sig = self._signer(exe)
                    except Exception:
                        sig = "Unknown"
                    if sig != "Signed":          # Microsoft vb. geçerli imzalı güncelleyiciler gürültü yapmasın
                        why = "imzasız" if sig == "Unsigned" else "imzası doğrulanamadı"
                        events.append({"kaynak": "surec", "seviye": "dikkat", "baslik": "Riskli bir yoldan program başladı",
                                       "metin": f"{name} ({exe}) İndirilenler/Temp gibi bir klasörden çalışmaya başladı ve {why}. "
                                                "Sen açtıysan sorun yok; açmadıysan Görev Yöneticisi'nde yerini kontrol et.",
                                       "kisa": f"{name} programı İndirilenler ya da Temp klasöründen başladı ve {why}."})
            # sürekli yüksek işlemci (sistem boşta işlemi hariç)
            if name.lower() in ("system idle process", "idle") or pid == os.getpid():
                continue
            cpu = cpu / ncpu                 # psutil: tek çekirdek = %100; tüm işlemciye göre yüzde
            if cpu >= self.cpu_limit:
                self._hot[pid] = self._hot.get(pid, 0) + 1
                if self._hot[pid] >= self.cpu_polls and now - self._cpu_alerted.get(pid, 0) > 1800:
                    self._cpu_alerted[pid] = now
                    events.append({"kaynak": "surec", "seviye": "dikkat", "baslik": "Bir program işlemciyi yoruyor",
                                   "metin": f"{name} uzun süredir işlemciyi %{int(cpu)} civarında kullanıyor; bilgisayar "
                                            "yavaşlayabilir. Gerekmiyorsa kapatabilirsin ('{0} kapat' de).".format(name),
                                   "kisa": f"{name} uzun süredir işlemciyi çok kullanıyor."})
            else:
                self._hot.pop(pid, None)
        self._known = current
        for pid in list(self._hot):
            if pid not in current:
                self._hot.pop(pid, None)
        b = self._batt()
        if b:
            pct, plugged = b
            if pct <= 15 and not plugged and not self._batt_alert:
                self._batt_alert = True
                events.append({"kaynak": "pil", "seviye": "dikkat", "baslik": "Pil azaldı",
                               "metin": f"Pil %{int(pct)}; şarja takmazsan bilgisayar kapanabilir.",
                               "kisa": f"Pil yüzde {int(pct)}. Şarja tak."})
            elif pct > 25 or plugged:
                self._batt_alert = False
        return events


# ---------------------------------------------------------------- gözcü (iş parçacıkları)
def python_exe():
    exe = sys.executable
    if os.name == "nt":
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w):
            return w
    return exe


def project_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Gozcu:
    """İzleyicileri ayrı iş parçacıklarında çalıştırır; olayları on_event(ev) ile bildirir.
    is_app=True: FENIX penceresi açıkken çalışan sürüm (başlangıç bekçisini uygulamanın kendi döngüsü yapar)."""

    def __init__(self, settings, on_event, is_app=False):
        self.s = settings
        self.on_event = on_event
        self.is_app = is_app
        self._stop = threading.Event()
        self._paused_until = 0.0
        self._threads = []
        self._startup_alerted = set()

    # -- kontrol
    def paused(self):
        return time.time() < self._paused_until

    def pause(self, seconds=3600):
        self._paused_until = time.time() + seconds

    def resume(self):
        self._paused_until = 0.0

    def stop(self):
        self._stop.set()

    def _emit(self, ev):
        if self.paused() or self._stop.is_set():
            return
        try:
            self.on_event(ev)
        except Exception as e:
            print(f"[NÖBET] olay işlenemedi: {e}")

    def _loop(self, interval, fn, first_delay=0.0):
        if first_delay and self._stop.wait(first_delay):
            return
        while not self._stop.is_set():
            try:
                for ev in fn() or []:
                    self._emit(ev)
            except Exception as e:
                print(f"[NÖBET] {fn.__name__}: {e}")
            if self._stop.wait(interval):
                return

    def _startup_check(self):
        """Açılışta başlayan programlar: ağır modülleri yüklememek için kısa ömürlü ayrı işlemde bakılır."""
        try:
            r = subprocess.run([python_exe(), os.path.join(project_dir(), "nobet_main.py"), "--baslangic-kontrol"],
                               capture_output=True, text=True, timeout=120, cwd=project_dir(),
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            data = json.loads((r.stdout or "").strip().splitlines()[-1])
        except Exception:
            return []
        fresh = [e for e in (data.get("yeni") or []) + (data.get("degisen") or [])
                 if (e.get("ad"), e.get("komut")) not in self._startup_alerted]
        if not fresh:
            return []
        self._startup_alerted.update((e.get("ad"), e.get("komut")) for e in fresh)
        names = ", ".join(e.get("ad", "?") for e in fresh[:3]) + (f" ve {len(fresh) - 3} tane daha" if len(fresh) > 3 else "")
        lines = [f"  • {e.get('ad')}: {str(e.get('komut'))[:100]}" for e in fresh[:5]]
        return [{"kaynak": "baslangic", "seviye": "kritik", "baslik": "Açılışta başlayan programlarda değişiklik",
                 "metin": "Açılışta otomatik başlayan programlarda değişiklik var:\n" + "\n".join(lines) +
                          "\nSen kurmadıysan FENIX'i açıp 'başlangıç değişikliklerini göster' de.",
                 "kisa": f"Açılışta başlayan programlarda değişiklik: {names}. Sen kurmadıysan kontrol et."}]

    def start(self):
        s = self.s
        if s.get("indirilenler", True):
            dw = DownloadWatcher(defender=bool(s.get("defender_tara", True)))
            self._threads.append(threading.Thread(target=self._loop, args=(3.0, dw.poll), daemon=True))
        if s.get("pano", True):
            cw = ClipboardWatcher()
            self._threads.append(threading.Thread(target=self._loop, args=(1.0, cw.poll), daemon=True))
        if s.get("surecler", True):
            pw = ProcessWatcher()
            self._threads.append(threading.Thread(target=self._loop, args=(10.0, pw.poll, 15.0), daemon=True))
        mins = s.get("baslangic_dakika", 30)
        if not self.is_app and mins and mins > 0:
            self._threads.append(threading.Thread(
                target=self._loop, args=(max(5.0, mins) * 60, self._startup_check, 90.0), daemon=True))
        for t in self._threads:
            t.start()
        return self


# ---------------------------------------------------------------- işlem yönetimi (arayüz tarafı)
def available():
    """Nöbet modu için gerekenler: Windows + pystray (simge her zaman görünmeli, simge yoksa nöbet başlamaz)."""
    if os.name != "nt":
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("pystray") is not None
    except Exception:
        return False


def _read_pid():
    try:
        with open(PID_PATH, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def is_running():
    pid = _read_pid()
    if not pid:
        return False
    try:
        import psutil
        if psutil.pid_exists(pid):
            cmd = " ".join(psutil.Process(pid).cmdline()).lower()
            if "nobet_main" in cmd:
                return True
    except Exception:
        pass
    try:
        os.remove(PID_PATH)
    except OSError:
        pass
    return False


def start_background(wait=6.0):
    """Nöbet işlemini başlatır (zaten çalışıyorsa dokunmaz). -> çalışıyor mu"""
    if is_running():
        return True
    try:
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([python_exe(), os.path.join(project_dir(), "nobet_main.py")], cwd=project_dir(),
                         creationflags=flags, close_fds=True)
    except Exception as e:
        print(f"[NÖBET] başlatılamadı: {e}")
        return False
    end = time.time() + wait
    while time.time() < end:
        if is_running():
            return True
        time.sleep(0.2)
    return False


def stop_running():
    """Çalışan nöbet işlemini kapatır. -> kapatıldı mı"""
    pid = _read_pid()
    if not pid:
        return False
    try:
        import psutil
        p = psutil.Process(pid)
        if "nobet_main" in " ".join(p.cmdline()).lower():
            p.terminate()
            try:
                p.wait(3)
            except Exception:
                p.kill()
    except Exception:
        pass
    try:
        os.remove(PID_PATH)
    except OSError:
        pass
    return True


# ---------------------------------------------------------------- yan sohbet işlemi (nöbet tarafı)
CHAT_PID_PATH = os.path.join(DATA_DIR, "yan_sohbet.pid")
CHAT_SHOW_PATH = os.path.join(DATA_DIR, "yan_sohbet.goster")


def _chat_pid():
    try:
        with open(CHAT_PID_PATH, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def chat_running():
    pid = _chat_pid()
    if not pid:
        return False
    try:
        import psutil
        if psutil.pid_exists(pid):
            cmd = " ".join(psutil.Process(pid).cmdline()).lower()
            if "nobet_main" in cmd and "--sohbet" in cmd:
                return True
    except Exception:
        pass
    try:
        os.remove(CHAT_PID_PATH)
    except OSError:
        pass
    return False


def open_chat():
    """Yan sohbeti açar; zaten açıksa öne getirmesini ister. -> başlatıldı/öne getirildi mi"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if chat_running():
        try:
            with open(CHAT_SHOW_PATH, "w", encoding="utf-8") as f:
                f.write("1")
            return True
        except OSError:
            return False
    try:
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([python_exe(), os.path.join(project_dir(), "nobet_main.py"), "--sohbet"], cwd=project_dir(),
                         creationflags=flags, close_fds=True)
        return True
    except Exception as e:
        print(f"[NÖBET] yan sohbet açılamadı: {e}")
        return False


def stop_chat():
    """Açık yan sohbeti kapatır (kill-switch ve 'nöbeti bitir' bunu da kapatır). -> kapatıldı mı"""
    pid = _chat_pid()
    if not pid:
        return False
    try:
        import psutil
        p = psutil.Process(pid)
        cmd = " ".join(p.cmdline()).lower()
        if "nobet_main" in cmd and "--sohbet" in cmd:
            p.terminate()
            try:
                p.wait(3)
            except Exception:
                p.kill()
    except Exception:
        pass
    for path in (CHAT_PID_PATH, CHAT_SHOW_PATH):
        try:
            os.remove(path)
        except OSError:
            pass
    return True


# ---------------------------------------------------------------- nöbet işleminin kendisi
class _Voice:
    """Sesli uyarılar sırayla, kısa ömürlü ayrı işlemlerde okunur (RAM'i geri verir)."""

    def __init__(self, voice):
        self.voice = voice
        self.q = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text):
        self.q.put(text)

    def _run(self):
        while True:
            text = self.q.get()
            try:
                subprocess.run([python_exe(), os.path.join(project_dir(), "nobet_main.py"), "--soyle", text, self.voice],
                               timeout=120, cwd=project_dir(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                pass


def _rss_mb():
    try:
        import psutil
        return int(psutil.Process(os.getpid()).memory_info().rss / 1048576)
    except Exception:
        return 0


def _icon_image(paused=False):
    from PIL import Image, ImageDraw
    try:
        img = Image.open(os.path.join(project_dir(), "fenix.ico")).convert("RGBA").resize((64, 64))
    except Exception:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((6, 6, 58, 58), fill=(10, 20, 40, 255), outline=(0, 217, 255, 255), width=4)
        d.ellipse((24, 24, 40, 40), fill=(0, 217, 255, 255))
    if paused:
        img = img.convert("LA").convert("RGBA")
    return img


def speak_once(text, voice=None):
    """--soyle: metni bir kez okuyup çıkar (ses ayarlarını uygulamayla aynı yerden alır)."""
    from modules import audio_io
    try:
        from modules import user_settings
        v = user_settings.get("voice")
        if v:
            audio_io.set_prosody(**{k: x for k, x in v.items() if k in ("rate", "pitch", "volume")})
    except Exception:
        pass
    audio_io.speak(text, voice or "tr-TR-AhmetNeural")
    end = time.time() + 90
    time.sleep(0.5)
    while audio_io.is_speaking() and time.time() < end:
        time.sleep(0.3)


def startup_check_json():
    """--baslangic-kontrol: başlangıç değişikliklerini JSON olarak yazdırır (ayrı işlemde çalışır)."""
    from modules import functions as fx
    ch = fx.startup_changes()
    keep = lambda e: {"ad": e.get("ad"), "komut": str(e.get("komut"))[:200]}
    print(json.dumps({"yeni": [keep(e) for e in ch.get("yeni", [])],
                      "degisen": [keep(e) for e in ch.get("degisen", [])]}, ensure_ascii=False))


def run():
    """Nöbet işlemi: tepsi simgesi + gözcü. Simge yoksa (pystray kurulu değil) hiç başlamaz."""
    import yaml
    import pystray
    from . import notifier
    from .killswitch import KillSwitch, log_exit
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}
    from . import i18n
    i18n.init(cfg)
    settings = load_settings(cfg.get("nobet"))
    voice = (cfg.get("audio") or {}).get("tts_voice", "tr-TR-AhmetNeural")
    with open(PID_PATH, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    def cleanup():
        try:
            os.remove(PID_PATH)
        except OSError:
            pass
        try:
            stop_chat()                      # kill-switch / nöbeti bitir: açık yan sohbet de kapanır
        except Exception:
            pass

    ks = cfg.get("killswitch") or {}
    KillSwitch(ks.get("hotkey", "ctrl+alt+q"), ks.get("corner_trigger", True), ks.get("corner_size", 5),
               ks.get("corner_hold_seconds", 1.5), light=True, on_quit=cleanup).start()
    speaker = _Voice(voice)

    def on_event(ev):
        s = load_settings(cfg.get("nobet"))          # tepsiden değişen ses ayarı hemen geçerli olsun
        settings.update(s)
        from .i18n import tr as _t
        kisa = _t(ev["kisa"])
        notifier.show_toast_async("FENIX · " + _t(ev["baslik"]), kisa)
        if should_speak(settings["uyari_sesi"], ev["seviye"], quiet_now(settings.get("sessiz_saat"))):
            speaker.say(kisa)

    gozcu = Gozcu(settings, on_event).start()
    state = {"icon": None}
    chat_on = bool(settings.get("yan_sohbet", True))
    if chat_on and settings.get("yan_sohbet_kisayol"):
        try:
            import keyboard
            keyboard.add_hotkey(settings["yan_sohbet_kisayol"], open_chat)
        except Exception as e:
            print(f"[NÖBET] yan sohbet kısayolu kurulamadı: {e}")

    def open_chat_item(icon, item):
        open_chat()

    def set_level(level):
        def _do(icon, item):
            settings["uyari_sesi"] = level
            save_user_settings(uyari_sesi=level)
            icon.update_menu()
        return _do

    def is_level(level):
        return lambda item: settings["uyari_sesi"] == level

    def toggle_pause(icon, item):
        if gozcu.paused():
            gozcu.resume()
        else:
            gozcu.pause(3600)
        icon.icon = _icon_image(gozcu.paused())
        icon.update_menu()

    def open_app(icon, item):
        try:
            subprocess.Popen([python_exe(), os.path.join(project_dir(), "app.py")], cwd=project_dir(),
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0), close_fds=True)
        except Exception as e:
            print(f"[NÖBET] uygulama açılamadı: {e}")
            return
        quit_all(icon, item)

    def quit_all(icon, item):
        gozcu.stop()
        cleanup()
        icon.stop()

    from .i18n import tr as _t
    menu = pystray.Menu(
        pystray.MenuItem(lambda item: _t("Nöbette • {} MB").format(_rss_mb()) + (_t(" (duraklatıldı)") if gozcu.paused() else ""),
                         None, enabled=False),
        *([pystray.MenuItem(_t("💬 Yan sohbet (yazarak)"), open_chat_item, default=True)] if chat_on else []),
        pystray.MenuItem(_t("FENIX'i aç"), open_app, default=not chat_on),
        pystray.MenuItem(lambda item: _t("Devam et") if gozcu.paused() else _t("1 saat duraklat"), toggle_pause),
        pystray.MenuItem(_t("Sesli uyarı"), pystray.Menu(
            pystray.MenuItem(_t("Yalnızca önemliler"), set_level("onemli"), checked=is_level("onemli"), radio=True),
            pystray.MenuItem(_t("Hepsi"), set_level("hepsi"), checked=is_level("hepsi"), radio=True),
            pystray.MenuItem(_t("Sessiz (sadece bildirim)"), set_level("sessiz"), checked=is_level("sessiz"), radio=True))),
        pystray.MenuItem(_t("Nöbeti bitir (tamamen kapat)"), quit_all))
    icon = pystray.Icon("fenix_nobet", _icon_image(False), _t("FENIX nöbette"), menu)
    state["icon"] = icon

    def refresh():
        while True:
            time.sleep(30)
            try:
                icon.title = f"FENIX nöbette • {_rss_mb()} MB" + (" • duraklatıldı" if gozcu.paused() else "")
                icon.update_menu()
            except Exception:
                pass

    threading.Thread(target=refresh, daemon=True).start()
    try:
        icon.run()
    except Exception as e:
        log_exit(f"nöbet işlemi çöktü: {type(e).__name__}: {e}")
    finally:
        cleanup()
