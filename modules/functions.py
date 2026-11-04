# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Eller ve Aksiyon (v4)
---------------------
- Onay mekanizması UI'ya bağlanabilir: set_confirm_handler ile arayüzdeki modal
  kutuya yönlendirilir. UI yoksa (ör. PTT-only) tkinter messagebox'a düşer.
- Riskli komutlar otomatik tespit edilir ve HER MODDA onay ister (Devil dahil).
- "allow_actions=false" olan Güvenli mod'da bu fonksiyonlar modele hiç verilmez
  (llm_client tool listesini eklemez), yani çağrılamaz.
"""
from . import security as sec
import os
import re
import subprocess
import time
import threading
import queue

def _speak(*args, **kwargs):
    """Sesli okuma. audio_io (numpy, sounddevice, pygame, edge-tts) ilk konuşmada yüklenir; yazılı çalışan
    yan sohbet (v5.10.1) bu paketleri hiç yüklemez."""
    from .audio_io import speak as _real
    return _real(*args, **kwargs)


_SPEAK_REAL = _speak      # komut hafızası _speak'i geçici susturur; onay uyarısı yine de duyulsun

# UI tarafından set edilir: fn(title, message, detail) -> bool
_CONFIRM_HANDLER = None
# UI tarafından set edilir: fn(text) -> None  (pipeline/log'a bilgi basmak için)
_NOTIFY_HANDLER = None


def set_confirm_handler(fn):
    global _CONFIRM_HANDLER
    _CONFIRM_HANDLER = fn


def set_notify_handler(fn):
    global _NOTIFY_HANDLER
    _NOTIFY_HANDLER = fn


# UI tarafından set edilir: fn(where, detail) -> None  (hatayı Geçmiş'e not düşmek için)
_ERROR_HANDLER = None

GENERIC_ERROR = ("Bir hata ile karşılaştım. Ayrıntıyı hata notlarına kaydettim; "
                 "hata metnini sesli okumadan sadece 'hata ile karşılaştım' de.")


# Ekran yakalama (arayüz, FENIX penceresini gizleyerek yakalayan fonksiyonla değiştirir) ve
# görüntü yorumlama (LLMClient, Gemini ile tarif eden fonksiyonu verir)
_CAPTURE_HANDLER = None      # fn() -> base64 jpeg
_VISION_HANDLER = None       # fn(soru, base64) -> metin


def set_capture_handler(fn):
    global _CAPTURE_HANDLER
    _CAPTURE_HANDLER = fn


def set_vision_handler(fn):
    global _VISION_HANDLER
    _VISION_HANDLER = fn


def capture_screen():
    if _CAPTURE_HANDLER:
        return _CAPTURE_HANDLER()
    from . import screen_capture as sc
    return sc.capture_screen_base64()


class VisionError(Exception):
    pass


def _vision_why(e):
    """Görüntü hatasının kullanıcıya söylenecek sebebi. Her model için ayrı durum varsa onu verir."""
    summary = getattr(e, "summary", None)
    if summary:
        return summary
    t = str(e)
    return ("Gemini'nin kotası dolmuş" if ("429" in t or "RESOURCE_EXHAUSTED" in t) else
            "Gemini şu an çok yoğun, biraz sonra tekrar dene" if ("503" in t or "UNAVAILABLE" in t) else
            "Gemini modeli bulunamadı (config.yaml'daki gemini_model adını kontrol et)" if ("404" in t or "NOT_FOUND" in t)
            else "Gemini anahtarı geçersiz ya da eksik" if ("API key" in t or "401" in t or "403" in t or "PERMISSION" in t)
            else "Gemini yanıt vermedi")


def describe_screen(question=""):
    """Ekranı yakalar ve görüntü modeline tarif ettirir. Hata durumunda VisionError (anlaşılır mesajla)."""
    try:
        b64 = capture_screen()
    except Exception as e:
        report_error("ekran yakalama", e)
        raise VisionError("Ekran görüntüsü alınamadı (ayrıntı Geçmiş'teki hata notunda).")
    if not _VISION_HANDLER:
        raise VisionError("Görüntü modeli ayarlı değil (Gemini anahtarı gerekli).")
    try:
        return _VISION_HANDLER(question, b64)
    except Exception as e:
        report_error("ekran yorumlama (Gemini)", e)
        why = _vision_why(e)
        raise VisionError(f"Ekran görüntüsünü aldım ama görüntüyü yorumlayamadım: {why}.")


def describe_image_b64(b64, question="", name="görsel"):
    """Eklenen/yapıştırılan görseli tarif ettirir; hata olursa anlaşılır VisionError."""
    if not _VISION_HANDLER:
        raise VisionError("Görüntü modeli ayarlı değil (Gemini anahtarı gerekli).")
    try:
        return _VISION_HANDLER(question, b64, source="image")
    except TypeError:
        return _VISION_HANDLER(question, b64)
    except Exception as e:
        report_error("görsel yorumlama (Gemini)", f"{name}: {e}")
        why = _vision_why(e)
        raise VisionError(f"“{name}” görselini yorumlayamadım: {why}. (Görselleri sadece Gemini görebiliyor; "
                          "metin sohbeti Groq ile çalışmaya devam ediyor.)")


def look_at_screen(question: str = ""):
    """Model aracı: kullanıcının ekranına bakar, ne gördüğünü metin olarak döner."""
    _notify("Ekrana bakılıyor")
    try:
        return {"status": "ok", "ekranda_gorulen": describe_screen(question)}
    except VisionError as e:
        return {"status": "error", "message": str(e) + " Bunu kullanıcıya aynen söyle."}


def set_error_handler(fn):
    global _ERROR_HANDLER
    _ERROR_HANDLER = fn


def report_error(where, detail):
    """Hata ayrıntısını kenara not eder (kullanıcıya okunmaz)."""
    print(f"[HATA] {where}: {detail}")
    if _ERROR_HANDLER:
        try:
            _ERROR_HANDLER(where, str(detail))
        except Exception:
            pass


def _notify(text):
    if _NOTIFY_HANDLER:
        try:
            _NOTIFY_HANDLER(text)
        except Exception:
            pass


RISKY_PATTERNS = [
    "remove-item", "del ", "erase ", "rd ", "rmdir", "format", "diskpart",
    "shutdown", "restart-computer", "stop-computer", "clear-recyclebin",
    "taskkill", "reg delete", "remove-itemproperty", "net user", "uninstall",
    "stop-service", "disable-", "set-executionpolicy", "-recurse", "-force",
    "bcdedit", "cipher", "takeown", "icacls", "stop-process", "invoke-webrequest",
    "invoke-restmethod", "curl ", "wget ",
]


# PowerShell'in kısa adları (alias): "rm", "ri", "kill", "spps" de silme/sonlandırma yapar. Önceden yalnızca uzun
# adlar tanındığı için "rm dosya.txt" onay sorulmadan çalışabiliyordu (otomatik testler yakaladı).
_RISKY_ALIAS_RE = re.compile(r"(?:^|[\s;|&(`{])(?:rm|ri|rmdir|rd|del|erase|kill|spps|rni)(?=\s|$|;|\|)", re.IGNORECASE)


def _is_risky(command: str) -> bool:
    c = command.lower()
    return (any(p in c for p in RISKY_PATTERNS) or "remove-" in c or "clear-content" in c
            or bool(_RISKY_ALIAS_RE.search(command)))


def _safe_speak(text):
    try:
        _SPEAK_REAL(text)
    except Exception:
        pass


def _confirm(title, message, detail=""):
    """Onay iste. UI handler varsa onu kullan; yoksa tkinter messagebox."""
    # Sesli uyarı arka planda çalsın: onay kutusu konuşma bitene kadar beklemeden hemen açılsın
    threading.Thread(target=lambda: _safe_speak("Onayına ihtiyacım var."), daemon=True).start()
    if _CONFIRM_HANDLER:
        try:
            return bool(_CONFIRM_HANDLER(title, message, detail))
        except Exception:
            pass
    # Yedek: tkinter messagebox
    try:
        import tkinter as tk
        from tkinter import messagebox
        q = queue.Queue()

        def show():
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            msg = message + (f"\n\n{detail}" if detail else "")
            q.put(messagebox.askyesno(title, msg, parent=root))
            root.destroy()

        t = threading.Thread(target=show)
        t.start()
        t.join()
        return q.get()
    except Exception:
        return False


def _exec_ps(command: str, timeout: int = 45):
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", command],
            capture_output=True, text=True, timeout=timeout, creationflags=flags,
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if r.returncode == 0:
            return {"status": "ok", "message": out or "İşlem tamamlandı."}
        report_error("komut", err or f"Hata kodu: {r.returncode}\nKomut: {command}")
        return {"status": "error", "message": GENERIC_ERROR}
    except subprocess.TimeoutExpired:
        report_error("komut", f"Zaman aşımı ({timeout}s)\nKomut: {command}")
        return {"status": "error", "message": GENERIC_ERROR}
    except Exception as e:
        report_error("komut", f"{e}\nKomut: {command}")
        return {"status": "error", "message": GENERIC_ERROR}


# --- FONKSİYONLAR ---
WEB_COMMAND_PATTERNS = ["invoke-webrequest", "iwr ", "invoke-restmethod", "irm ", "curl ", "wget ",
                        "start-bitstransfer", "net.webclient", "downloadstring", "downloadfile"]


# PowerShell ile dosyaya içerik yazma kalıpları (Set-Content, Out-File, here-string @' ... '@ vb.)
_FILE_WRITE_RE = re.compile(r"set-content|add-content|out-file|\[io\.file\]::write|new-item[^\n|]*-value|>\s*['\"]?[^\s'\"]+\.\w{1,5}",
                            re.IGNORECASE)


def _writes_inline_file(command: str) -> bool:
    """Komut, uzun bir içeriği (kod/HTML/metin) dosyaya yazıyor mu? Bunun yerine write_file kullanılmalı:
    onay kutusunu sayfalarca komutla doldurmaz, Türkçe karakter/tırnak kaçış sorunu da olmaz."""
    heredoc = "@'" in command or '@"' in command
    return (heredoc or len(command) > 1200) and bool(_FILE_WRITE_RE.search(command))


def run_command(command: str, description: str):
    # Web'e PowerShell ile erişme girişimlerini onay kutusuna düşürmeden geri çevir:
    # sayfa okumak/aramak için arka plan araçları var (onay istemez, tarayıcı açmaz).
    if any(w in command.lower() for w in WEB_COMMAND_PATTERNS):
        _notify(f"Engellendi (web komutu): {description}")
        return {"status": "error",
                "message": ("Web'e PowerShell ile erişme. Sayfa okumak için read_webpage, arama için "
                            "search_web aracını kullan; bunlar onay istemez ve tarayıcı açmaz.")}
    if _writes_inline_file(command):
        _notify(f"Yönlendirildi (dosya yazma aracı): {description}")
        return {"status": "error",
                "message": ("Dosyaya kod/HTML/metin yazmak için run_command KULLANMA. write_file aracını çağır: "
                            "path (ör. 'masaüstü/muzik_studyosu/index.html') ve content (dosyanın tam içeriği). "
                            "Birden fazla dosya gerekiyorsa her biri için ayrı write_file çağır.")}
    _notify(f"İşlem: {description}")
    if _is_risky(command):
        if not _confirm("Kritik İşlem", description, f"Komut:\n{command}"):
            return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    else:
        try:
            _speak(description)
        except Exception:
            pass
    return _exec_ps(command)


def open_app_by_name(app_name: str):
    _notify(f"Uygulama açılıyor: {app_name}")
    ps = (
        f"$a = Get-StartApps | Where-Object {{ $_.Name -like '*{app_name}*' }} | Select-Object -First 1; "
        f"if ($a) {{ Start-Process \"shell:AppsFolder\\$($a.AppID)\"; Write-Output \"Acildi: $($a.Name)\" }} "
        f"else {{ Write-Output 'BULUNAMADI' }}"
    )
    try:
        _speak(f"{app_name} açılıyor")
    except Exception:
        pass
    return _exec_ps(ps)


_OPEN_TIMES = []          # son open_url çağrı zamanları (sekme sayısını sınırlamak için)
_MAX_TABS_PER_MIN = 3


def open_url(url: str, browser_name: str = None):
    now = time.time()
    _OPEN_TIMES[:] = [t for t in _OPEN_TIMES if now - t < 60]
    if len(_OPEN_TIMES) >= _MAX_TABS_PER_MIN:
        return {"status": "error",
                "message": ("Tarayıcıda dakikada en fazla %d sekme açılabilir. Araştırma için "
                            "tarayıcı açma; read_webpage ile sayfaları arka planda oku." % _MAX_TABS_PER_MIN)}
    _OPEN_TIMES.append(now)
    if not url.startswith("http"):
        url = "https://" + url
    _notify(f"Site açılıyor: {url}")
    if browser_name:
        exe = browser_name.lower().strip()
        if not exe.endswith(".exe"):
            exe += ".exe"
        ps = (
            f"$p='HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}'; "
            f"$b=(Get-ItemProperty -Path $p -ErrorAction SilentlyContinue).'(default)'; "
            f"if ($b) {{ Start-Process -FilePath $b -ArgumentList '{url}'; Write-Output 'Acildi' }} "
            f"else {{ Start-Process '{url}'; Write-Output 'Varsayilan tarayicida acildi' }}"
        )
    else:
        ps = f"Start-Process '{url}'"
    try:
        _speak(f"{url} açılıyor")
    except Exception:
        pass
    return _exec_ps(ps)


def read_webpage(url: str):
    """Sayfayı TARAYICI AÇMADAN arka planda çeker; başlık, metin ve aynı siteye giden linkleri döner."""
    from . import web_analyzer as wa
    _notify(f"Sayfa okunuyor: {url}")
    rep = wa.fetch_and_parse(url, timeout=20, max_chars=4000)
    if "error" in rep:
        report_error("sayfa okuma", f"{url}: {rep['error']}")
        return {"status": "error", "message": GENERIC_ERROR}
    return {"status": "ok", "url": rep["final_url"], "http": rep["status_code"], "title": rep["title"],
            "headings": rep["headings"][:10], "text": rep["text_excerpt"], "links": rep.get("links", [])[:12]}


_SEARCH_KEYS = {"tavily": "", "brave": ""}
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/128.0 Safari/537.36")


def set_search_keys(keys):
    """Arayüz config.yaml'daki arama API anahtarlarını buraya verir (tavily / brave, isteğe bağlı)."""
    for k in _SEARCH_KEYS:
        v = (keys or {}).get(k) or ""
        _SEARCH_KEYS[k] = "" if str(v).startswith("BURAYA") else str(v).strip()


def _search_tavily(query, n):
    import requests
    r = requests.post("https://api.tavily.com/search", timeout=20,
                      json={"api_key": _SEARCH_KEYS["tavily"], "query": query, "max_results": n})
    r.raise_for_status()
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")[:300]}
            for x in r.json().get("results", [])]


def _search_brave(query, n):
    import requests
    r = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": n},
                     headers={"X-Subscription-Token": _SEARCH_KEYS["brave"], "Accept": "application/json"},
                     timeout=20)
    r.raise_for_status()
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("description", "")}
            for x in r.json().get("web", {}).get("results", [])]


def _search_ddg_html(query, n):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, parse_qs, unquote
    r = requests.post("https://html.duckduckgo.com/html/", data={"q": query}, headers={"User-Agent": _UA}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for res in soup.select(".result")[:n]:
        a = res.select_one(".result__a")
        if not a:
            continue
        href = a.get("href", "")
        qs = parse_qs(urlparse(href).query)
        if "uddg" in qs:
            href = unquote(qs["uddg"][0])
        snip = res.select_one(".result__snippet")
        out.append({"title": a.get_text(strip=True), "url": href,
                    "snippet": snip.get_text(" ", strip=True) if snip else ""})
    return out


def _search_ddg_lite(query, n):
    import requests
    from bs4 import BeautifulSoup
    r = requests.post("https://lite.duckduckgo.com/lite/", data={"q": query}, headers={"User-Agent": _UA}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    links = soup.select("a.result-link")
    snips = soup.select("td.result-snippet")
    return [{"title": a.get_text(strip=True), "url": a.get("href", ""),
             "snippet": snips[i].get_text(" ", strip=True) if i < len(snips) else ""}
            for i, a in enumerate(links[:n])]


def _unwrap_bing(href):
    """Bing bazen sonuç linklerini bing.com/ck/a?...&u=a1<base64> izleme adresine sarar; asıl adresi çıkarır."""
    import base64
    from urllib.parse import urlparse, parse_qs
    if "bing.com/ck/a" not in href:
        return href
    try:
        u = parse_qs(urlparse(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            u = u[2:]
        return base64.urlsafe_b64decode(u + "=" * (-len(u) % 4)).decode("utf-8", "ignore") or href
    except Exception:
        return href


def _search_bing(query, n):
    import requests
    from bs4 import BeautifulSoup
    r = requests.get("https://www.bing.com/search", params={"q": query, "setlang": "tr"},
                     headers={"User-Agent": _UA, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"}, timeout=20)
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for li in soup.select("li.b_algo")[:n]:
        a = li.select_one("h2 a")
        if not a:
            continue
        p = li.select_one(".b_caption p") or li.select_one("p")
        out.append({"title": a.get_text(strip=True), "url": _unwrap_bing(a.get("href", "")),
                    "snippet": p.get_text(" ", strip=True) if p else ""})
    return out


def search_web(query: str):
    """Arama yapar (tarayıcı açmadan). Sırayla dener: Tavily / Brave (anahtar varsa) ->
    DuckDuckGo -> DuckDuckGo Lite -> Bing. İlk sonuç veren motoru kullanır."""
    _notify(f"Aranıyor: {query}")
    engines = []
    if _SEARCH_KEYS["tavily"]:
        engines.append(("Tavily", _search_tavily))
    if _SEARCH_KEYS["brave"]:
        engines.append(("Brave", _search_brave))
    engines += [("DuckDuckGo", _search_ddg_html), ("DuckDuckGo Lite", _search_ddg_lite), ("Bing", _search_bing)]
    problems = []
    for name, fn in engines:
        try:
            results = [r for r in fn(query, 8) if r.get("url", "").startswith("http")]
        except Exception as e:
            problems.append(f"{name}: {str(e)[:120]}")
            continue
        if results:
            return {"status": "ok", "engine": name, "results": results}
        problems.append(f"{name}: sonuç yok")
    report_error("web arama", f"'{query}' için hiçbir arama motoru sonuç vermedi -> " + " | ".join(problems))
    return {"status": "error", "message": "Arama sonucu alınamadı; bilinen adresleri read_webpage ile oku."}


def open_folder_by_name(folder_name: str, base_dir: str = None):
    _notify(f"Klasör aranıyor: {folder_name}")
    base_map = {
        "desktop": "$env:USERPROFILE\\Desktop", "masaüstü": "$env:USERPROFILE\\Desktop",
        "downloads": "$env:USERPROFILE\\Downloads", "indirilenler": "$env:USERPROFILE\\Downloads",
        "documents": "$env:USERPROFILE\\Documents", "belgeler": "$env:USERPROFILE\\Documents",
    }
    base = base_map.get((base_dir or "desktop").lower().strip(), "$env:USERPROFILE\\Desktop")
    ps = (
        f"$m = Get-ChildItem -Path {base} -Recurse -Directory -Filter '*{folder_name}*' "
        f"-ErrorAction SilentlyContinue | Select-Object -First 1; "
        f"if ($m) {{ Invoke-Item $m.FullName; Write-Output \"Acildi: $($m.FullName)\" }} "
        f"else {{ Write-Output 'BULUNAMADI' }}"
    )
    try:
        _speak(f"{folder_name} klasörü açılıyor")
    except Exception:
        pass
    return _exec_ps(ps)


def set_system_volume(level: int):
    _notify(f"Ses seviyesi: %{level}")
    try:
        _speak(f"Ses seviyesi yüzde {level}")
    except Exception:
        pass
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        dev = AudioUtilities.GetSpeakers()
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(max(0, min(level, 100)) / 100, None)
        return {"status": "ok", "message": f"Ses %{level}."}
    except Exception as e:
        report_error("ses seviyesi", e)
        return {"status": "error", "message": GENERIC_ERROR}


# =====================================================================
#  v5.6.2 ARAÇLARI: dosyalar, ses ayarı, hatırlatıcı, kısayollar, unutma
# =====================================================================
import fnmatch
import datetime as _dt

_MEMORY = None          # app tarafından verilir (unutma, hatırlatma sohbet bağı)
_REMINDERS = None       # ReminderStore


def set_memory(mem):
    global _MEMORY
    _MEMORY = mem


def set_reminder_store(store):
    global _REMINDERS
    _REMINDERS = store


# ---------------- dosya/klasör ----------------
_SKIP_DIRS = {"node_modules", ".git", "venv", ".venv", "env", "__pycache__", "appdata", "$recycle.bin", ".cache",
              "dist", "build", ".next", ".idea", ".vscode", "site-packages", "chroma_db", ".gradle", "target"}


def _ascii(t):
    return (t or "").lower().translate(str.maketrans("çğıöşüâî", "cgiosuai")).strip()


def _alias_dirs():
    home = os.path.expanduser("~")
    od = os.environ.get("OneDrive") or os.path.join(home, "OneDrive")
    cand = {
        "masaustu": [os.path.join(home, "Desktop"), os.path.join(od, "Desktop"), os.path.join(od, "Masaüstü")],
        "desktop": [os.path.join(home, "Desktop"), os.path.join(od, "Desktop")],
        "belgeler": [os.path.join(home, "Documents"), os.path.join(od, "Documents"), os.path.join(od, "Belgeler")],
        "documents": [os.path.join(home, "Documents"), os.path.join(od, "Documents")],
        "indirilenler": [os.path.join(home, "Downloads")],
        "downloads": [os.path.join(home, "Downloads")],
        "resimler": [os.path.join(home, "Pictures"), os.path.join(od, "Pictures")],
        "ev": [home], "kullanici": [home], "home": [home],
    }
    return {k: [p for p in dict.fromkeys(v) if os.path.isdir(p)] for k, v in cand.items()}


def resolve_folders(folder):
    """'masaüstü', 'belgeler/okul', 'C:\\Users\\..\\proje' gibi ifadeleri gerçek klasör listesine çevirir."""
    folder = (folder or "masaüstü").strip().strip('"')
    if os.path.isabs(folder) or (len(folder) > 1 and folder[1] == ":"):
        return [folder] if os.path.isdir(folder) else []
    parts = re.split(r"[\\/]", folder, maxsplit=1)
    aliases = _alias_dirs()
    key = _ascii(parts[0])
    bases = aliases.get(key)
    if bases is None:
        # bilinmeyen ad: masaüstü ve belgeler altında bu adda bir klasör ara (1-2 seviye)
        out = []
        for b in aliases.get("masaustu", []) + aliases.get("belgeler", []):
            for root, dirs, _ in os.walk(b):
                if root[len(b):].count(os.sep) >= 2:
                    dirs[:] = []
                    continue
                dirs[:] = [d for d in dirs if d.lower() not in _SKIP_DIRS]
                for d in dirs:
                    if _ascii(folder) in _ascii(d):
                        out.append(os.path.join(root, d))
            if out:
                break
        return out[:3]
    if len(parts) > 1:
        return [os.path.join(b, parts[1]) for b in bases if os.path.isdir(os.path.join(b, parts[1]))]
    return bases


def resolve_file(path):
    path = (path or "").strip().strip('"')
    if os.path.isfile(path):
        return path
    parts = re.split(r"[\\/]", path)
    if len(parts) > 1:
        for base in resolve_folders(parts[0]):
            cand = os.path.join(base, *parts[1:])
            if os.path.isfile(cand):
                return cand
    for base in resolve_folders("masaüstü"):
        cand = os.path.join(base, path)
        if os.path.isfile(cand):
            return cand
    return None


def _fmt_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def find_files(name: str = "", folder: str = "masaüstü", content: str = "", extension: str = ""):
    """Dosya arar (tarayıcı/terminal açmadan). name: ad parçası ya da *.py gibi kalıp; content: dosya içinde
    geçen metin (metin/kod dosyalarında); extension: .py gibi."""
    from .attachments import TEXT_EXT
    import time as _t
    roots = resolve_folders(folder)
    if not roots:
        return {"status": "error", "message": f"'{folder}' klasörü bulunamadı."}
    _notify(f"Dosya aranıyor: {name or extension or content} ({folder})")
    ext = extension.lower() if extension else ""
    if ext and not ext.startswith("."):
        ext = "." + ext
    pat = name.lower()
    results, scanned, start = [], 0, _t.time()
    for root_dir in roots:
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d.lower() not in _SKIP_DIRS and not d.startswith(".")]
            if root[len(root_dir):].count(os.sep) > 6:
                dirs[:] = []
            for f in files:
                scanned += 1
                fl = f.lower()
                if ext and not fl.endswith(ext):
                    continue
                if pat and not (fnmatch.fnmatch(fl, pat) if any(c in pat for c in "*?") else _ascii(pat) in _ascii(fl)):
                    continue
                full = os.path.join(root, f)
                hit = None
                if content:
                    if os.path.splitext(fl)[1] not in TEXT_EXT:
                        continue
                    try:
                        if os.path.getsize(full) > 2 * 1024 * 1024:
                            continue
                        with open(full, encoding="utf-8", errors="ignore") as fh:
                            for ln, line in enumerate(fh, 1):
                                if content.lower() in line.lower():
                                    hit = f"satır {ln}: {line.strip()[:160]}"
                                    break
                    except Exception:
                        continue
                    if not hit:
                        continue
                try:
                    st = os.stat(full)
                    results.append({"yol": full, "boyut": _fmt_size(st.st_size),
                                    "degisti": _dt.datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M"),
                                    **({"eslesme": hit} if hit else {})})
                except Exception:
                    continue
                if len(results) >= 40:
                    break
            if len(results) >= 40 or scanned > 60000 or _t.time() - start > 8:
                break
    note = "" if (scanned <= 60000 and _t.time() - start <= 8) else " (arama sınırına ulaşıldı, daha dar bir klasör ver)"
    return {"status": "ok", "bulunan": len(results), "sonuclar": results,
            "aranan_klasorler": roots, "not": f"{scanned} dosya tarandı{note}"}


def list_folder(folder: str = "masaüstü"):
    roots = resolve_folders(folder)
    if not roots:
        return {"status": "error", "message": f"'{folder}' klasörü bulunamadı."}
    out = []
    for r in roots:
        try:
            entries = sorted(os.scandir(r), key=lambda e: (not e.is_dir(), e.name.lower()))
        except Exception as e:
            out.append({"klasor": r, "hata": str(e)})
            continue
        items = []
        for e in entries[:200]:
            try:
                items.append(("📁 " if e.is_dir() else "📄 ") + e.name +
                             ("" if e.is_dir() else f"  ({_fmt_size(e.stat().st_size)})"))
            except Exception:
                pass
        out.append({"klasor": r, "ogeler": items, "toplam": len(entries)})
    return {"status": "ok", "klasorler": out}


_READ_FULL_LIMIT = 5000        # bu kadar karaktere kadar dosyanın tamamı döner (Groq'un dakikalık sınırına sığsın)
_READ_PART_LIMIT = 5000        # arama / satır aralığı sonucunun üst sınırı
_LANDMARK_RE = re.compile(
    r"<\s*(header|nav|main|section|article|aside|footer|form|script|style|head|body)\b[^>]*>"
    r"|^\s*(?:def|class|async def)\s+\w+|^\s*(?:function\s+\w+|const\s+\w+\s*=\s*(?:\(|function)|class\s+\w+)"
    r"|^\s*(?:#{1,3}\s+\S|/\*\s*[=\-]{2,}|//\s*[=\-]{2,}|<!--)",
    re.IGNORECASE)


def _numbered(lines, start, end):
    return "\n".join(f"{n}| {lines[n - 1]}" for n in range(start, end + 1))


def read_file(path: str, question: str = "", find: str = "", start_line: int = 0, end_line: int = 0):
    """Dosyayı okur (metin/kod/PDF/Word/Excel/resim). Sisteme dokunmaz.
    Büyük dosyada tamamını değil, başını ve 'içindekiler' listesini (bölümlerin satır numaraları) döner;
    find: aranan metnin geçtiği yerleri çevresiyle, start_line/end_line: o satırları (numaralı) döner."""
    from . import attachments as att
    full = resolve_file(path)
    if not full:
        return {"status": "error", "message": f"'{path}' bulunamadı. Önce find_files ile ara."}
    _notify(f"Dosya okunuyor: {os.path.basename(full)}")
    try:
        item = att.load(full)
    except att.AttachmentError as e:
        return {"status": "error", "message": str(e)}
    if item["kind"] == "image":
        try:
            return {"status": "ok", "yol": full, "gorsel_tarifi": describe_image_b64(item["image_b64"], question,
                                                                                    item["name"])}
        except VisionError as e:
            return {"status": "error", "message": str(e)}
    text = item["text"]
    lines = text.splitlines()
    total = len(lines)
    base = {"status": "ok", "yol": full, "bilgi": item.get("info", ""), "toplam_satir": total,
            "toplam_karakter": len(text)}
    if item.get("note"):
        base["not"] = item["note"]

    # 1) Arama: aranan metnin geçtiği satırlar, ±6 satır çevresiyle
    if find and find.strip():
        terms = [t.strip().lower() for t in re.split(r"[,;|]", find) if t.strip()]
        hits = [n for n, ln in enumerate(lines, 1) if any(t in ln.lower() for t in terms)]
        if not hits:
            base.update(bulunan_yer=0, message=f"'{find}' dosyada geçmiyor. Başka bir kelimeyle ara ya da "
                                               "start_line/end_line ile bir bölümü oku.")
            return base
        windows = []
        for n in hits:
            a, b = max(1, n - 6), min(total, n + 6)
            if windows and a <= windows[-1][1] + 1:
                windows[-1][1] = max(windows[-1][1], b)
            else:
                windows.append([a, b])
        parts, used = [], 0
        for a, b in windows:
            chunk = _numbered(lines, a, b)
            if used + len(chunk) > _READ_PART_LIMIT:
                parts.append("… (başka eşleşmeler de var; aramayı daralt ya da start_line/end_line kullan)")
                break
            parts.append(chunk)
            used += len(chunk)
        base.update(bulunan_yer=len(hits), eslesen_satirlar=hits[:50], icerik="\n...\n".join(parts),
                    ipucu="Bir kısmı değiştirmek için edit_file kullan (old_text = değişecek metnin aynısı).")
        return base

    # 2) Satır aralığı
    if start_line or end_line:
        a = max(1, int(start_line or 1))
        b = min(total, int(end_line or a + 120))
        if a > total:
            base.update(message=f"Dosya {total} satır; {a}. satır yok.")
            return base
        chunk, n = [], a
        while n <= b and sum(len(c) for c in chunk) < _READ_PART_LIMIT:
            chunk.append(f"{n}| {lines[n - 1]}")
            n += 1
        base.update(satirlar=f"{a}-{n - 1}", icerik="\n".join(chunk))
        if n - 1 < b:
            base["devami"] = f"Sınır nedeniyle {n - 1}. satırda kesildi; devamı için start_line={n} ile çağır."
        return base

    # 3) Küçük dosya: tamamı
    if len(text) <= _READ_FULL_LIMIT:
        base["icerik"] = text
        return base

    # 4) Büyük dosya: başı + içindekiler (bölümlerin satır numaraları)
    # Tekrar eden işaretler (120 tane <section> gibi) listeyi doldurup footer'ı dışarıda bırakmasın:
    # her türden ilk 3'ü yazılır, kalanı tek satırda özetlenir.
    marks, seen = [], {}
    for n, ln in enumerate(lines, 1):
        mt = _LANDMARK_RE.search(ln)
        if not mt:
            continue
        kind = (mt.group(1) or mt.group(0).strip().split()[0][:12]).lower()
        info = seen.setdefault(kind, [0, n, n])
        info[0] += 1
        info[2] = n
        if info[0] <= 3:
            marks.append((n, f"{n}| {ln.strip()[:90]}"))
    for kind, (cnt, first, last) in seen.items():
        if cnt > 3:
            marks.append((last, f"… '{kind}' toplam {cnt} kez (satır {first}–{last}); arada kalanlar için start_line/end_line"))
    marks = [t for _, t in sorted(marks)][:60]
    head, used, n = [], 0, 0
    while n < total and used < 1800:
        head.append(f"{n + 1}| {lines[n]}")
        used += len(lines[n]) + 6
        n += 1
    base.update(kisaltildi=True, dosyanin_basi="\n".join(head), icindekiler=marks,
                ipucu=("Dosya büyük, tamamı gönderilmedi. İlgili yeri görmek için read_file'ı find (ör. 'footer') ya "
                       "da start_line/end_line ile tekrar çağır. Değiştirmek için edit_file kullan; bütün dosyayı "
                       "write_file ile yeniden yazma."))
    return base


# ---------------- dosyanın bir parçasını düzenleme ----------------
_EDITABLE_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".ts", ".jsx", ".tsx", ".json", ".py", ".md", ".txt",
                 ".yaml", ".yml", ".xml", ".csv", ".ini", ".cfg", ".toml", ".svg", ".php", ".java", ".c", ".cpp",
                 ".h", ".cs", ".go", ".rb", ".sql", ".bat", ".ps1", ".sh"}


def edit_file(path: str, old_text: str, new_text: str = "", reason: str = ""):
    """Metin/kod dosyasında BİR parçayı değiştirir ya da siler (new_text boşsa). Bütün dosyayı yeniden yazmaz.
    old_text dosyada tam olarak bir kez geçmeli. Onay kutusu çıkar; değişiklikten önce yedek alınır."""
    full = resolve_file(path)
    if not full:
        return {"status": "error", "message": f"'{path}' bulunamadı. Önce find_files ile ara."}
    if os.path.splitext(full)[1].lower() not in _EDITABLE_EXT:
        return {"status": "error", "message": "Bu araç sadece metin/kod dosyalarını düzenler (Word/PDF/Excel değil)."}
    if not old_text:
        return {"status": "error", "message": "old_text boş. Önce read_file (find ile) değişecek metni al."}
    try:
        with open(full, encoding="utf-8", newline="") as f:
            content = f.read()
    except UnicodeDecodeError:
        return {"status": "error", "message": "Dosya UTF-8 metin değil, bu araçla düzenlenemez."}
    except Exception as e:
        report_error("dosya düzenleme", f"{full}: {e}")
        return {"status": "error", "message": GENERIC_ERROR}
    old = old_text
    count = content.count(old)
    if count == 0 and "\r\n" in content and "\r\n" not in old:      # Windows satır sonları
        old = old.replace("\n", "\r\n")
        new_text = (new_text or "").replace("\r\n", "\n").replace("\n", "\r\n")
        count = content.count(old)
    if count == 0:
        return {"status": "error", "message": ("old_text dosyada birebir bulunamadı. read_file'ı find ile çağırıp metni "
                                               "satır numaraları OLMADAN, boşlukları dahil aynen kopyala.")}
    if count > 1:
        return {"status": "error", "message": (f"old_text dosyada {count} yerde geçiyor. Tek bir yeri seçmek için "
                                               "çevresinden birkaç satır daha ekleyerek benzersiz yap.")}
    first_line = content[:content.index(old)].count("\n") + 1
    shown_old = old_text if len(old_text) <= 700 else old_text[:700] + f"\n… (+{len(old_text) - 700} karakter)"
    shown_new = (new_text or "") if len(new_text or "") <= 700 else new_text[:700] + "\n…"
    if not _confirm("Dosya düzenlenecek", f"{os.path.basename(full)} ({first_line}. satır civarı)"
                    + (f" — {reason}" if reason else ""),
                    f"Çıkarılacak:\n{shown_old}\n\nYerine:\n{shown_new or '(hiçbir şey, bu kısım silinecek)'}\n\n"
                    "Önce dosyanın yedeği alınır."):
        return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    backup_dir = os.path.abspath(os.path.join("data", "yedekler"))
    try:
        os.makedirs(backup_dir, exist_ok=True)
        backup = os.path.join(backup_dir, f"{time.strftime('%Y%m%d_%H%M%S')}_{os.path.basename(full)}")
        with open(backup, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(content.replace(old, new_text or "", 1))
    except Exception as e:
        report_error("dosya düzenleme", f"{full}: {e}")
        return {"status": "error", "message": GENERIC_ERROR}
    _notify(f"Dosya düzenlendi: {os.path.basename(full)} ({first_line}. satır)")
    return {"status": "ok", "yol": full, "satir": first_line,
            "degisen": "silindi" if not new_text else "değiştirildi", "yedek": backup,
            "not": "Sonucu kontrol etmek için read_file'ı find ya da start_line ile çağırabilirsin."}


def write_file(path: str, content: str, overwrite: bool = False):
    """Yeni dosya yazar (kod, not, ödev). Var olan dosyanın üzerine yazmak onay ister."""
    path = (path or "").strip().strip('"')
    if not path:
        return {"status": "error", "message": "Dosya yolu boş."}
    if not (os.path.isabs(path) or (len(path) > 1 and path[1] == ":")):
        parts = re.split(r"[\\/]", path, maxsplit=1)
        bases = resolve_folders(parts[0]) if len(parts) > 1 else []
        if bases:
            path = os.path.join(bases[0], parts[1])
        else:
            desk = resolve_folders("masaüstü")
            path = os.path.join(desk[0] if desk else os.path.expanduser("~"), path)
    path = os.path.abspath(path)
    home = os.path.abspath(os.path.expanduser("~"))
    if len(content or "") > 2 * 1024 * 1024:
        return {"status": "error", "message": "İçerik çok büyük (2 MB sınırı)."}
    outside = not path.lower().startswith(home.lower())
    if os.path.exists(path):
        if not overwrite:
            return {"status": "error", "message": "Bu dosya zaten var. Üzerine yazmak için kullanıcıya sor; isterse "
                                                  "overwrite=true ile tekrar çağır (onay kutusu çıkar)."}
        if not _confirm("Dosyanın üzerine yazılacak", os.path.basename(path), f"Yol:\n{path}"):
            return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    elif outside and not _confirm("Kullanıcı klasörü dışına dosya yazılacak", os.path.basename(path), f"Yol:\n{path}"):
        return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    ext = os.path.splitext(path)[1].lower()
    if ext in (".docx", ".pdf"):
        # Word/PDF düz metin olarak yazılırsa dosya bozuk açılır: içerik Markdown kabul edilip gerçek belgeye çevrilir.
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            from . import report_export
            md = (content or "").replace("\\n", "\n")         # model bazen satır sonunu kaçışlı yazıyor
            (report_export.export_docx if ext == ".docx" else report_export.export_pdf)(md, path)
        except Exception as e:
            report_error("belge yazma", f"{path}: {e}")
            return {"status": "error", "message": GENERIC_ERROR}
        _notify(f"Belge oluşturuldu: {path}")
        return {"status": "ok", "yol": path, "bicim": ext[1:], "boyut": _fmt_size(os.path.getsize(path))}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        from . import imza
        content = imza.sign_code(path, content or "")        # imza yorumu program tarafından eklenir (v5.10.2)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")
    except Exception as e:
        report_error("dosya yazma", f"{path}: {e}")
        return {"status": "error", "message": GENERIC_ERROR}
    _notify(f"Dosya yazıldı: {path}")
    return {"status": "ok", "yol": path, "boyut": _fmt_size(len((content or '').encode('utf-8')))}


# ---------------- ses ayarı ----------------
def set_voice(rate: str = "", pitch: str = "", volume: str = "", reset: bool = False):
    """FENIX'in konuşma sesini ayarlar (bilgisayarın ses seviyesi DEĞİL). rate: '-20%' (yavaş) .. '+30%' (hızlı);
    pitch: '-10Hz' (kalın) .. '+10Hz' (ince); volume: '-30%' .. '+30%'."""
    from . import audio_io, user_settings

    def clamp(val, lo, hi, unit):
        m = re.match(r"^\s*([+-]?\d+)\s*", str(val))
        if not m:
            return None
        n = max(lo, min(hi, int(m.group(1))))
        return f"{n:+d}{unit}"

    cur = audio_io.get_prosody()
    if reset:
        new = {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%"}
    else:
        new = dict(cur)
        if rate:
            new["rate"] = clamp(rate, -50, 60, "%") or cur["rate"]
        if pitch:
            new["pitch"] = clamp(pitch, -30, 30, "Hz") or cur["pitch"]
        if volume:
            new["volume"] = clamp(volume, -60, 60, "%") or cur["volume"]
    audio_io.set_prosody(**new)
    user_settings.set("voice", new)
    _notify(f"Ses ayarı: hız {new['rate']}, ton {new['pitch']}, seviye {new['volume']}")
    return {"status": "ok", "onceki": cur, "yeni": new}


# ---------------- hatırlatıcı ----------------
def set_reminder(when: str, text: str):
    from .reminders import parse_when, human_when
    if not _REMINDERS:
        return {"status": "error", "message": "Hatırlatıcı hazır değil."}
    due = parse_when(when)
    if not due:
        return {"status": "error", "message": f"'{when}' zamanını anlayamadım. 'YYYY-AA-GG SS:DD' biçiminde ver."}
    if due <= _dt.datetime.now():
        return {"status": "error", "message": "Bu zaman geçmişte kalıyor."}
    rid = _REMINDERS.add(due, text, getattr(_MEMORY, "current_session_id", None))
    _notify(f"Hatırlatma kuruldu: {human_when(due)} — {text}")
    return {"status": "ok", "id": rid, "zaman": due.strftime("%Y-%m-%d %H:%M"), "okunusu": human_when(due),
            "metin": text}


def list_reminders():
    from .reminders import human_when
    if not _REMINDERS:
        return {"status": "error", "message": "Hatırlatıcı hazır değil."}
    return {"status": "ok", "hatirlatmalar": [{"id": r["id"], "zaman": human_when(r["due"]), "metin": r["text"]}
                                              for r in _REMINDERS.pending()]}


def cancel_reminder(id: int):
    if not _REMINDERS:
        return {"status": "error", "message": "Hatırlatıcı hazır değil."}
    ok = _REMINDERS.cancel(int(id))
    return {"status": "ok" if ok else "error", "message": "İptal edildi." if ok else "Bu numarada bekleyen hatırlatma yok."}


# ---------------- kısayol komutları ----------------
def save_shortcut(name: str, steps: list):
    from . import macros
    try:
        n, s = macros.save(name, steps if isinstance(steps, list) else [steps])
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    _notify(f"Kısayol kaydedildi: {n} ({len(s)} adım)")
    return {"status": "ok", "ad": n, "adimlar": s, "kullanim": f"'{n}' demen yeterli."}


def list_shortcuts():
    from . import macros
    return {"status": "ok", "kisayollar": macros.load()}


def delete_shortcut(name: str):
    from . import macros
    return {"status": "ok"} if macros.delete(name) else {"status": "error", "message": "Bu adda kısayol yok."}


# ---------------- sistem röntgeni (KENDİ bilgisayar - Devil modda en güçlü) ----------------
def _startup_programs():
    """Windows başlangıcında otomatik açılan programlar (inspect_system için özet; ayrıntı _startup_entries'te)."""
    return [{"ad": x["ad"], "komut": x["komut"][:160], "nerede": _SRC_LABEL.get(x["kaynak"], x["kaynak"])}
            for x in _startup_entries()][:40]


def inspect_system(focus: str = ""):
    """KENDİ bilgisayarının anlık durumunu çıkarır: en çok CPU/RAM kullanan süreçler, başlangıçta otomatik
    açılan programlar, dinleyen (LISTEN) yerel portlar, disk doluluğu. Sadece OKUR, hiçbir şeyi değiştirmez
    ya da kapatmaz; 'şunu kapat/kaldır' istenirse run_command ile ayrı onaylı bir işlem gerekir."""
    import psutil
    _notify("Sistem inceleniyor")
    out = {"status": "ok"}
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                info = p.info
                mem_mb = (info["memory_info"].rss / (1024 * 1024)) if info["memory_info"] else 0
                try:
                    cpu = p.cpu_percent(interval=None)
                except Exception:
                    cpu = 0.0
                procs.append({"pid": info["pid"], "ad": info["name"], "cpu_%": round(cpu, 1),
                              "ram_mb": round(mem_mb, 1)})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        out["en_cok_ram_kullanan"] = sorted(procs, key=lambda x: -x["ram_mb"])[:10]
        out["en_cok_cpu_kullanan"] = sorted(procs, key=lambda x: -x["cpu_%"])[:10]
        out["toplam_surec_sayisi"] = len(procs)
    except Exception as e:
        out["surec_hatasi"] = str(e)[:160]

    try:
        listening, seen = [], set()
        for c in psutil.net_connections(kind="inet"):
            if c.status == psutil.CONN_LISTEN and c.laddr and (c.laddr.port, c.pid) not in seen:
                seen.add((c.laddr.port, c.pid))
                pname = "?"
                if c.pid:
                    try:
                        pname = psutil.Process(c.pid).name()
                    except Exception:
                        pass
                listening.append({"port": c.laddr.port, "program": pname})
        out["dinleyen_portlar"] = sorted(listening, key=lambda x: x["port"])[:40]
    except Exception as e:
        out["port_hatasi"] = str(e)[:160] + " (bazı bilgiler için Yönetici olarak çalıştırmak gerekebilir)"

    try:
        out["baslangic_programlari"] = _startup_programs()
    except Exception as e:
        out["baslangic_hatasi"] = str(e)[:160]

    try:
        disks = []
        for part in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(part.mountpoint)
                disks.append({"surucu": part.device, "toplam_gb": round(u.total / 1e9, 1),
                              "bos_gb": round(u.free / 1e9, 1), "kullanim_%": u.percent})
            except Exception:
                continue
        out["diskler"] = disks
    except Exception as e:
        out["disk_hatasi"] = str(e)[:160]
    return out


# ---------------- kendi proje klasörü güvenlik kontrolü (yayına çıkmadan önce) ----------------
_PROJECT_KEY_PATTERNS = [
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("Stripe Live Key", re.compile(r"\bsk_live_[0-9A-Za-z]{20,}\b")),
    ("Genel Secret/Token", re.compile(r"(?i)(?:secret|api[_-]?key|token|password)\s*[:=]\s*['\"][A-Za-z0-9+/_\-]{16,}['\"]")),
    ("Özel Anahtar (PEM)", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
]
_ENV_NAMES = {".env", ".env.local", ".env.production", ".env.development", ".env.staging"}


def check_project_security(folder: str = "masaüstü"):
    """KENDİ proje klasörünü yayına çıkmadan/GitHub'a göndermeden önce kontrol eder: .env dosyaları
    .gitignore'a eklenmiş mi, kod içinde unutulmuş anahtar/şifre KALIBI var mı (değer gösterilmez,
    sadece dosya+satır), .git deposu var mı. Sadece KENDİ diskindeki dosyaları okur, dışarıya hiçbir
    şey göndermez."""
    roots = resolve_folders(folder)
    if not roots:
        return {"status": "error", "message": f"'{folder}' klasörü bulunamadı."}
    _notify(f"Proje güvenlik kontrolü: {folder}")
    root = roots[0]
    out = {"status": "ok", "klasor": root, "env_dosyalari": [], "gitignore_durumu": None,
          "olasi_anahtarlar": [], "git_deposu_var": os.path.isdir(os.path.join(root, ".git"))}

    gitignore_path = os.path.join(root, ".gitignore")
    gitignore_lines = []
    if os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, encoding="utf-8", errors="ignore") as f:
                gitignore_lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
        except Exception:
            pass
        out["gitignore_durumu"] = "var"
    else:
        out["gitignore_durumu"] = "yok (tüm dosyalar yanlışlıkla commit edilebilir)"

    def _env_ignored(name):
        return any(pat in (".env", ".env*") or fnmatch.fnmatch(name, pat) for pat in gitignore_lines)

    scanned, start = 0, time.time()
    for cur, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in _SKIP_DIRS and not d.startswith(".")]
        for fname in files:
            scanned += 1
            full = os.path.join(cur, fname)
            if fname in _ENV_NAMES:
                out["env_dosyalari"].append({"yol": full, "gitignore_de_korunuyor": _env_ignored(fname)})
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yaml", ".yml", ".env",
                           ".php", ".java", ".go", ".rb", ".txt", ".md", ".config", ".ini"):
                continue
            if fname == ".gitignore" or os.path.getsize(full) > 2 * 1024 * 1024:
                continue
            try:
                with open(full, encoding="utf-8", errors="ignore") as fh:
                    for ln, line in enumerate(fh, 1):
                        for ad, pat in _PROJECT_KEY_PATTERNS:
                            if pat.search(line):
                                out["olasi_anahtarlar"].append({"yol": full, "satir": ln, "tur": ad,
                                                               "not": "değer burada gösterilmiyor, dosyayı aç ve kontrol et"})
                                break
            except Exception:
                continue
            if scanned > 8000 or time.time() - start > 10:
                break
        if scanned > 8000 or time.time() - start > 10:
            break
    out["olasi_anahtarlar"] = out["olasi_anahtarlar"][:30]
    _notify(f"Proje kontrolü tamamlandı: {len(out['env_dosyalari'])} .env, "
           f"{len(out['olasi_anahtarlar'])} olası anahtar izi")
    return out


# ---------------- pasif site güvenlik/durum gözlemi ----------------
def inspect_website_security(url: str):
    """Bir web sitesi için PASİF güvenlik/durum gözlemleri çıkarır: TLS/sertifika durumu, DNS/WHOIS kaydı,
    robots.txt/sitemap, teknoloji parmak izi, eksik HTTP güvenlik başlıkları. SADECE herkese açık, GET/TLS
    el sıkışması ile okunabilen bilgidir; şifre denemez, zafiyet/sızma denemesi YAPMAZ. Amaç site sahibini
    eksikler konusunda yapıcı şekilde bilgilendirmektir, saldırmak değildir."""
    from . import web_analyzer as wa
    _notify(f"Güvenlik gözlemi: {url}")
    page = wa.fetch_and_parse(url, timeout=20, max_chars=500)
    if "error" in page:
        report_error("site güvenlik gözlemi", f"{url}: {page['error']}")
        return {"status": "error", "message": GENERIC_ERROR}
    try:
        sec = wa.security_inspect(url)
    except Exception as e:
        report_error("site güvenlik gözlemi", e)
        sec = {}
    out = {"status": "ok", "url": sec.get("url", page.get("final_url", url)), "sunucu": page.get("server"),
          "eksik_guvenlik_basliklari": page.get("missing_security_headers", [])}
    out.update({k: v for k, v in sec.items() if k not in ("url", "host")})
    return out


# ======================================================================
# v5.7.2 GÜVENLİK GÜNCELLEMESİ
#   Tespit (salt okuma, Güvenli modda da var):
#     check_windows_security, find_suspicious_processes, watch_startup_programs
#   Müdahale (her biri FENIX onay kutusu ister; Güvenli modda modele hiç verilmez):
#     stop_process, remove_startup_program, restore_startup_program, enable_protection
#   Hiçbir dosyanın içeriği okunmaz, dışarıya hiçbir şey gönderilmez, hiçbir şey kalıcı silinmez
#   (başlangıçtan kaldırılanların yedeği tutulur, geri yüklenebilir).
# ======================================================================
import json as _json
import shutil as _shutil
import datetime as _dtm

_SEC_DIR = os.path.join("data", "guvenlik")
_STARTUP_BASELINE_PATH = os.path.join(_SEC_DIR, "baslangic_taban.json")
_STARTUP_BACKUP_PATH = os.path.join(_SEC_DIR, "baslangic_yedek.json")
_STARTUP_QUARANTINE_DIR = os.path.join(_SEC_DIR, "kaldirilan_kisayollar")
_SEC_LOCK = threading.Lock()


# ---- yardımcılar ----
def _ps_run(command, timeout=30):
    """PowerShell'i sessizce çalıştırır (hata notu düşmez: bu sorgular bazı sistemlerde doğal olarak boş döner).
    Dönüş: (çıkış_kodu, stdout). Windows dışında (-1, '')."""
    if os.name != "nt":
        return -1, ""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + command],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode, (r.stdout or "").strip()
    except Exception:
        return -1, ""


def _ps_json(command, timeout=30):
    code, out = _ps_run(command, timeout)
    if code != 0 or not out:
        return None
    try:
        return _json.loads(out)
    except Exception:
        return None


def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _psq(s):
    """PowerShell tek tırnaklı metin (içerideki ' iki kez yazılır)."""
    return "'" + str(s).replace("'", "''") + "'"


def _is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run_elevated(ps_command, timeout=120):
    """Komutu yönetici olarak çalıştırır. FENIX yönetici değilse Windows'un kendi UAC onay penceresi çıkar.
    Dönüş: (başarılı_mı, açıklama)."""
    if os.name != "nt":
        return False, "Bu işlem yalnızca Windows'ta yapılabilir."
    script = "$ErrorActionPreference='Stop'; " + ps_command
    if _is_admin():
        code, _ = _ps_run(script, timeout)
        return code == 0, "" if code == 0 else "Komut başarısız oldu."
    import base64
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    wrapper = ("try { $p = Start-Process -FilePath powershell -Verb RunAs -Wait -PassThru -WindowStyle Hidden "
               f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand','{enc}' -ErrorAction Stop; "
               "exit $p.ExitCode } catch { exit 1223 }")
    code, _ = _ps_run(wrapper, timeout)
    if code == 0:
        return True, ""
    if code == 1223:
        return False, "Windows yönetici onayı (UAC) verilmedi."
    return False, "Komut yönetici olarak çalıştırıldı ama başarısız oldu."


def _reg_read(hive_name, path, value):
    try:
        import winreg
        hive = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[hive_name]
        with winreg.OpenKey(hive, path) as k:
            return winreg.QueryValueEx(k, value)[0]
    except Exception:
        return None


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _other_antivirus():
    """Windows Güvenlik Merkezi'ne kayıtlı, Defender dışındaki antivirüs adları."""
    av = _as_list(_ps_json("Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct "
                           "| Select-Object displayName | ConvertTo-Json -Compress"))
    names = [a.get("displayName") for a in av if isinstance(a, dict) and a.get("displayName")]
    return [n for n in names if "defender" not in n.lower()]


_FW_QUERY = ("Get-NetFirewallProfile | Select-Object Name,@{n='On';e={[string]$_.Enabled}} "
             "| ConvertTo-Json -Compress")
_FW_NAMES = {"Domain": "Etki alanı ağı", "Private": "Özel ağ", "Public": "Ortak ağ"}
_MP_QUERY = ("Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled,AntivirusSignatureAge,"
             "AMRunningMode,IsTamperProtected | ConvertTo-Json -Compress")

_HOWTO = {
    "defender": "Başlat → Windows Güvenliği → Virüs ve tehdit koruması → Ayarları yönet → Gerçek zamanlı koruma: Açık.",
    "tanim": "Windows Güvenliği → Virüs ve tehdit koruması → Koruma güncelleştirmeleri → Güncelleştirmeleri denetle.",
    "kurcalama": "Windows Güvenliği → Virüs ve tehdit koruması → Ayarları yönet → Kurcalama Koruması: Açık.",
    "firewall": "Başlat → Windows Güvenliği → Güvenlik duvarı ve ağ koruması → kapalı görünen ağ türüne tıkla → Açık.",
    "smartscreen": "Windows Güvenliği → Uygulama ve tarayıcı denetimi → İtibar tabanlı koruma → hepsini Açık yap.",
    "uac": "Başlat'a 'UAC' yaz → Kullanıcı Hesabı Denetimi ayarlarını değiştir → kaydırıcıyı en az 3. seviyeye al → Tamam → yeniden başlat.",
    "update": "Ayarlar → Windows Update → Güncelleştirmeleri denetle.",
}


# ---- 1) Windows güvenlik durumu (salt okuma) ----
def check_windows_security():
    """Bilgisayarın temel korumalarını OKUR, hiçbir ayarı değiştirmez: antivirüs / Defender gerçek zamanlı
    koruma ve tanım yaşı, kurcalama koruması, güvenlik duvarı (her ağ türü), SmartScreen, UAC, son Windows
    güncellemesi. Kapalı/eski olan her şey için nasıl açılacağını söyler."""
    if os.name != "nt":
        return {"status": "error", "message": "Bu kontrol yalnızca Windows'ta çalışır."}
    _notify("Windows güvenlik durumu kontrol ediliyor")
    acik, uyarilar, okunamayan = [], [], []

    def warn(konu, howto_key, fenix_acabilir=None):
        item = {"konu": konu, "nasil_acilir": _HOWTO[howto_key]}
        if fenix_acabilir:
            item["fenix_acabilir"] = fenix_acabilir
        uyarilar.append(item)

    # Antivirüs / Defender
    others = _other_antivirus()
    mp = _ps_json(_MP_QUERY)
    if isinstance(mp, dict):
        passive = "passive" in str(mp.get("AMRunningMode") or "").lower()
        if mp.get("RealTimeProtectionEnabled") is True and not passive:
            acik.append("Microsoft Defender gerçek zamanlı koruma açık")
            age = mp.get("AntivirusSignatureAge")
            if isinstance(age, int) and age > 7:
                warn(f"Defender virüs tanımları {age} gündür güncellenmemiş", "tanim")
            elif isinstance(age, int):
                acik.append(f"Virüs tanımları güncel ({age} gün önce)")
            if mp.get("IsTamperProtected") is False:
                warn("Kurcalama Koruması kapalı: zararlı bir program Defender'ı sessizce kapatabilir", "kurcalama")
        elif others:
            acik.append(f"Koruma başka bir antivirüste: {', '.join(others)} (Defender bu yüzden pasif)")
        else:
            warn("Defender gerçek zamanlı koruma KAPALI ve başka antivirüs görünmüyor", "defender", "defender")
    elif others:
        acik.append(f"Antivirüs: {', '.join(others)}")
    else:
        okunamayan.append("Defender/antivirüs durumu")

    # Güvenlik duvarı
    fw = [p for p in _as_list(_ps_json(_FW_QUERY)) if isinstance(p, dict)]
    if fw:
        off = [_FW_NAMES.get(p.get("Name"), p.get("Name")) for p in fw if p.get("On") != "True"]
        if off:
            warn(f"Güvenlik duvarı kapalı: {', '.join(off)}", "firewall", "firewall")
        else:
            acik.append("Güvenlik duvarı tüm ağ türlerinde açık")
    else:
        okunamayan.append("Güvenlik duvarı")

    # SmartScreen (önce grup ilkesi, sonra kullanıcı ayarı; kayıt yoksa Windows varsayılanı = açık)
    pol = _reg_read("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableSmartScreen")
    if pol is not None:
        ss_off = str(pol) == "0"
    else:
        val = _reg_read("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer", "SmartScreenEnabled")
        ss_off = val is not None and str(val).lower() == "off"
    if ss_off:
        warn("SmartScreen kapalı: indirilen tanınmayan programlar uyarısız açılır", "smartscreen")
    else:
        acik.append("SmartScreen açık")

    # UAC
    lua = _reg_read("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA")
    prompt = _reg_read("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
                       "ConsentPromptBehaviorAdmin")
    if lua is None:
        okunamayan.append("UAC")
    elif str(lua) == "0":
        warn("UAC tamamen KAPALI: programlar sana sormadan yönetici yetkisi alabilir", "uac")
    elif prompt is not None and str(prompt) == "0":
        warn("UAC sessiz modda: yönetici isteyen programlar sormadan onaylanıyor", "uac")
    else:
        acik.append("UAC (Kullanıcı Hesabı Denetimi) açık")

    # Son Windows güncellemesi
    hf = _ps_json("Get-HotFix | Where-Object InstalledOn | Sort-Object InstalledOn -Descending | "
                  "Select-Object -First 1 HotFixID,@{n='Tarih';e={$_.InstalledOn.ToString('yyyy-MM-dd')}} "
                  "| ConvertTo-Json -Compress", timeout=45)
    if isinstance(hf, dict) and hf.get("Tarih"):
        try:
            days = (_dtm.date.today() - _dtm.date.fromisoformat(hf["Tarih"])).days
        except Exception:
            days = None
        if days is not None and days > 45:
            warn(f"Son Windows güncellemesi {days} gün önce ({hf.get('HotFixID')})", "update")
        else:
            acik.append(f"Son Windows güncellemesi {hf['Tarih']} ({hf.get('HotFixID')})")
    else:
        okunamayan.append("Windows güncelleme geçmişi")

    out = {"status": "ok", "acik_olanlar": acik, "uyarilar": uyarilar,
           "ozet": ("Temel korumaların hepsi açık görünüyor." if not uyarilar
                    else f"{len(uyarilar)} konuda dikkat gerekiyor.")}
    if okunamayan:
        out["okunamayanlar"] = okunamayan
    if any("fenix_acabilir" in u for u in uyarilar):
        out["not"] = ("Bu kontrol hiçbir ayarı değiştirmedi. 'fenix_acabilir' olanları kullanıcı İSTERSE "
                      "enable_protection ile açabilirsin (FENIX onayı + Windows yönetici onayı sorulur).")
    return out


# ---- 2) Başlangıç programları: kayıt, kalıcı taban, değişiklik tespiti ----
_RUN_KEYS = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
    ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
]
_SRC_LABEL = {"HKCU": "Kayıt Defteri (bu kullanıcı)", "HKLM": "Kayıt Defteri (tüm kullanıcılar)",
              "KLASOR_KULLANICI": "Başlangıç klasörü", "KLASOR_ORTAK": "Ortak Başlangıç klasörü"}


def _startup_folders():
    return [("KLASOR_KULLANICI", os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                                              "Start Menu", "Programs", "Startup")),
            ("KLASOR_ORTAK", os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Microsoft",
                                          "Windows", "Start Menu", "Programs", "StartUp"))]


def _startup_entries():
    """Açılışta otomatik başlayan her şey: Run/RunOnce kayıt anahtarları + iki Başlangıç klasörü."""
    items = []
    try:
        import winreg
        hives = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
        for hname, path in _RUN_KEYS:
            try:
                with winreg.OpenKey(hives[hname], path) as key:
                    i = 0
                    while True:
                        try:
                            name, value, vtype = winreg.EnumValue(key, i)
                        except OSError:
                            break
                        items.append({"ad": name, "komut": str(value), "kaynak": hname, "anahtar": path,
                                      "tur": vtype})
                        i += 1
            except OSError:
                continue
    except ImportError:
        pass        # Windows dışı
    for src, folder in _startup_folders():
        try:
            for f in sorted(os.listdir(folder)):
                if f.lower() == "desktop.ini":
                    continue
                items.append({"ad": f, "komut": f"(Başlangıç klasöründe dosya) {f}", "kaynak": src,
                              "yol": os.path.join(folder, f)})
        except OSError:
            continue
    return items


def startup_entry_key(e):
    return f"{e['kaynak']}|{e.get('anahtar') or ''}|{e['ad'].lower()}"


def _public_entry(e):
    d = {"ad": e["ad"], "nerede": _SRC_LABEL.get(e["kaynak"], e["kaynak"]), "komut": e["komut"][:220]}
    if "onceki_komut" in e:
        d["onceki_komut"] = e["onceki_komut"][:220]
    return d


def _save_baseline(entries):
    _save_json(_STARTUP_BASELINE_PATH, {"alindi": _dtm.datetime.now().isoformat(timespec="seconds"),
                                        "kayitlar": {startup_entry_key(e): e["komut"] for e in entries}})


def _exe_from_command(cmd):
    """Başlangıç komutundan program yolu ('"C:\\x\\a.exe" --arg' ya da 'C:\\x\\a.exe -arg'); bulunamazsa None."""
    m = re.match(r'\s*"([^"]+?\.exe)"', cmd or "", re.I) or re.match(r'\s*([A-Za-z]:\\.*?\.exe)\b', cmd or "", re.I)
    return os.path.expandvars(m.group(1)) if m else None


def _same_program_new_version(old, new):
    """Onayladığın (tabandaki) program aynı dosya adı ve aynı ürün klasörüyle yalnızca sürüm klasörü değişerek
    güncellendiyse (…\\OneDrive\\26.1\\x.exe -> …\\OneDrive\\26.2\\x.exe) yeniden sormaz."""
    a, b = _exe_from_command(old), _exe_from_command(new)
    if not a or not b:
        return False
    pa, pb = a.replace("/", "\\").lower().split("\\"), b.replace("/", "\\").lower().split("\\")
    return len(pa) == len(pb) and len(pa) >= 4 and pa[-1] == pb[-1] and pa[:-2] == pb[:-2] and pa[-2] != pb[-2]


def _drop_signed(entries):
    """Değişiklik listesinden, programı geçerli dijital imzalı olanları çıkarır (OneDrive/Edge/Teams gibi güncellenen
    programlar her sürümde yolunu değiştirir; bunlar için uyarmak gürültüdür). İmzasız ya da doğrulanamayan kalır.
    Not: geçerli imza 'güvenli' demek değildir, 'kim yazdığı doğrulanabiliyor' demektir."""
    if not entries:
        return entries
    try:
        paths = {}
        for e in entries:
            exe = _exe_from_command(e.get("komut", ""))
            if exe and os.path.isfile(exe):
                paths[id(e)] = exe
        if not paths:
            return entries
        sigs = sec._signatures(list(dict.fromkeys(paths.values())))
        return [e for e in entries if not (id(e) in paths and sigs.get(paths[id(e)]) == "Signed")]
    except Exception:
        return entries


def startup_changes():
    """Diskteki tabana göre yeni / komutu değişmiş başlangıç girdileri. Taban yoksa oluşturur.
    Tabanı DEĞİŞTİRMEZ (uyarı, kullanıcı 'ben kurdum' diyene kadar geçerli kalır). Arka plan bekçisi de bunu kullanır."""
    with _SEC_LOCK:
        entries = _startup_entries()
        base = _load_json(_STARTUP_BASELINE_PATH, None)
        if not isinstance(base, dict) or not isinstance(base.get("kayitlar"), dict):
            _save_baseline(entries)
            return {"ilk_olcum": True, "yeni": [], "degisen": [], "toplam": len(entries)}
        known = base["kayitlar"]
        yeni, degisen = [], []
        for e in entries:
            k = startup_entry_key(e)
            if k not in known:
                yeni.append(e)
            elif known[k] != e["komut"]:
                degisen.append(dict(e, onceki_komut=known[k]))
        degisen = [e for e in degisen if not _same_program_new_version(e.get('onceki_komut'), e['komut'])]
        n_all = len(yeni) + len(degisen)
        yeni, degisen = _drop_signed(yeni), _drop_signed(degisen)       # v5.10.2: geçerli imzalılar uyarı çıkarmaz
        return {"ilk_olcum": False, "yeni": yeni, "degisen": degisen, "toplam": len(entries),
                "imzali_sessiz": n_all - len(yeni) - len(degisen), "taban_tarihi": base.get("alindi")}


def watch_startup_programs(accept_current: bool = False):
    """Başlangıç programlarını diskte saklanan tabanla karşılaştırır (bilgisayar yeniden başlasa da taban kalır).
    Yeni eklenen ya da komutu değiştirilen girdileri bildirir. accept_current=True: kullanıcı değişiklikleri
    kendisinin yaptığını söyledi, şu anki liste yeni taban olur."""
    _notify("Başlangıç programları kontrol ediliyor")
    if accept_current:
        with _SEC_LOCK:
            entries = _startup_entries()
            _save_baseline(entries)
        return {"status": "ok", "toplam": len(entries),
                "ozet": "Şu anki başlangıç listesi güvenilir kabul edildi; bundan sonra sadece yeni değişiklikler bildirilecek."}
    ch = startup_changes()
    if ch["ilk_olcum"]:
        return {"status": "ok", "toplam": ch["toplam"],
                "ozet": ("İlk ölçüm alındı ve kaydedildi. Bundan sonra başlangıca eklenen ya da değiştirilen her "
                         "program fark edilecek (arka plan bekçisi de düzenli kontrol eder).")}
    if not ch["yeni"] and not ch["degisen"]:
        return {"status": "ok", "toplam": ch["toplam"], "taban_tarihi": ch.get("taban_tarihi"),
                "ozet": "Başlangıç programlarında değişiklik yok."}
    return {"status": "uyari",
            "ozet": f"{len(ch['yeni'])} yeni, {len(ch['degisen'])} komutu değişmiş başlangıç girdisi var.",
            "yeni_programlar": [_public_entry(e) for e in ch["yeni"]],
            "komutu_degisenler": [_public_entry(e) for e in ch["degisen"]],
            "taban_tarihi": ch.get("taban_tarihi"),
            "not": ("Kullanıcıya bunları kendisinin kurup kurmadığını sor. Kurduysa accept_current=true ile tekrar "
                    "çağır. Tanımıyorsa ve kaldırmak isterse remove_startup_program kullan (onay sorulur). Kullanıcı "
                    "açıkça istemeden hiçbir şeyi kaldırma.")}


# ---- 3) Şüpheli süreç taraması (salt okuma) ----
_SYSTEM_BINARIES = {"svchost.exe", "csrss.exe", "lsass.exe", "winlogon.exe", "services.exe", "smss.exe",
                    "wininit.exe", "spoolsv.exe", "taskhostw.exe", "dwm.exe", "conhost.exe", "rundll32.exe",
                    "dllhost.exe", "ctfmon.exe", "sihost.exe", "explorer.exe", "regsvr32.exe", "mshta.exe",
                    "wscript.exe", "cscript.exe", "fontdrvhost.exe", "runtimebroker.exe", "searchhost.exe",
                    "audiodg.exe", "wmiprvse.exe", "lsaiso.exe", "taskmgr.exe", "cmd.exe", "powershell.exe"}
# Kapatılırsa sistem çöker / oturum kapanır: bunlar Windows klasöründen çalışıyorsa asla sonlandırılmaz
_CRITICAL_NAMES = {"system", "system idle process", "registry", "memory compression", "secure system",
                   "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe",
                   "lsaiso.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe", "explorer.exe", "msmpeng.exe",
                   "sihost.exe", "ctfmon.exe", "audiodg.exe"}


def _lev(a, b):
    """Düzenleme mesafesi; yan yana iki harfin yer değiştirmesi (scvhost/svchost) tek hata sayılır."""
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def _lookalike(name):
    """'svch0st.exe', 'scvhost.exe' gibi sistem dosyası taklidi isimler."""
    n = name.lower()
    if n in _SYSTEM_BINARIES or n in ("iexplore.exe", "taskhost.exe") or not n.endswith(".exe"):
        return None
    base = n[:-4]
    for s in _SYSTEM_BINARIES:
        sb = s[:-4]
        if len(sb) < 5 or abs(len(sb) - len(base)) > 2:
            continue
        if _lev(base, sb) <= (1 if len(sb) < 8 else 2):
            return s
    return None


def _location_reasons(exe):
    p = exe.lower()
    env = lambda k, d="": (os.environ.get(k) or d).lower().rstrip("\\")
    temp, up = env("TEMP"), env("USERPROFILE")
    public = env("PUBLIC", r"c:\users\public")
    roots = {env("APPDATA"), env("LOCALAPPDATA"), env("PROGRAMDATA", r"c:\programdata")} - {""}
    r = []
    if (temp and p.startswith(temp + "\\")) or "\\temp\\" in p:
        r.append("Geçici dosyalar (Temp) klasöründen çalışıyor")
    if up and p.startswith(up + "\\downloads\\"):
        r.append("İndirilenler klasöründen çalışıyor")
    if public and p.startswith(public + "\\"):
        r.append("Ortak kullanıcı (Public) klasöründen çalışıyor")
    if "\\$recycle.bin\\" in p:
        r.append("Geri Dönüşüm Kutusu'ndan çalışıyor")
    if os.path.dirname(p) in roots:
        r.append("AppData/ProgramData kökünden çalışıyor (normal programlar kendi alt klasörünü kullanır)")
    return r


def _signatures(paths):
    """Windows'un kendi imza doğrulaması (Get-AuthenticodeSignature). Dönüş: {yol_küçük: (durum, imzalayan)}."""
    if not paths:
        return {}
    arr = ",".join(_psq(p) for p in paths)
    data = _as_list(_ps_json(
        f"Get-AuthenticodeSignature -LiteralPath @({arr}) -ErrorAction SilentlyContinue | Select-Object Path,"
        "@{n='S';e={[string]$_.Status}},@{n='Who';e={$_.SignerCertificate.Subject}} | ConvertTo-Json -Compress",
        timeout=60))
    out = {}
    for d in data:
        if isinstance(d, dict) and d.get("Path"):
            who = d.get("Who") or ""
            m = re.search(r"CN=\"?([^,\"]+)", who)
            out[d["Path"].lower()] = (d.get("S") or "?", m.group(1).strip() if m else "")
    return out


_KERNEL_VIRTUAL = {"system", "system idle process", "registry", "memory compression", "secure system",
                   "vmmem", "vmmemwsl", "vmcompute"}   # dosyası olmayan sanal/çekirdek süreçler: 'silinmiş' sayılmaz


def find_suspicious_processes():
    """Çalışan süreçlerde zararlı yazılımların tipik izlerini arar (salt okuma, hiçbir şeyi kapatmaz):
    sistem dosyası adını taşıyıp Windows klasörü dışından çalışanlar, sistem adını taklit eden isimler,
    Temp / İndirilenler / Public / AppData kökünden çalışanlar, dosyası diskten silinmiş halde çalışanlar.
    Adaylar Windows'un imza doğrulamasından geçirilir; geçerli imzalı sıradan durumlar elenir."""
    import psutil
    _notify("Şüpheli süreç taraması")
    windir = (os.environ.get("WINDIR") or r"C:\Windows").lower().rstrip("\\")
    cands, total = [], 0
    for p in psutil.process_iter(["pid", "name", "exe", "ppid"]):
        total += 1
        try:
            name, exe = p.info.get("name") or "", p.info.get("exe") or ""
        except Exception:
            continue
        if not exe or p.info["pid"] in (0, 4):
            continue
        nl = name.lower()
        if nl in _KERNEL_VIRTUAL and not re.match(r"^[a-z]:\\", exe, re.I):
            continue            # Registry / Memory Compression gibi diskte dosyası olmayan çekirdek süreçleri
        strong, weak = [], []
        if nl in _SYSTEM_BINARIES and not exe.lower().startswith(windir + "\\"):
            strong.append(f"Windows sistem dosyası adını ({name}) taşıyor ama Windows klasörü dışından çalışıyor")
        look = _lookalike(name)
        if look:
            weak.append(f"Adı bir sistem dosyasına ({look}) çok benziyor")
        weak += _location_reasons(exe)
        try:
            if not os.path.exists(exe) and re.match(r"^[a-z]:\\", exe, re.I):
                strong.append("Çalıştığı dosya diskten silinmiş")
        except Exception:
            pass
        if strong or weak:
            try:
                parent = psutil.Process(p.info["ppid"]).name() if p.info.get("ppid") else ""
            except Exception:
                parent = ""
            cands.append({"pid": p.info["pid"], "ad": name, "yol": exe, "strong": strong, "weak": weak,
                          "ust_surec": parent})
    cands = cands[:30]
    sigs = _signatures(sorted({c["yol"] for c in cands if os.path.exists(c["yol"])}))
    found, filtered = [], 0
    for c in cands:
        st, who = sigs.get(c["yol"].lower(), ("?", ""))
        valid = st == "Valid"
        if valid and not c["strong"]:
            filtered += 1        # ör. Temp'ten çalışan imzalı bir kurulum programı: olağan
            continue
        if st == "Valid":
            imza = f"Geçerli imza: {who or 'bilinmeyen yayıncı'}"
        elif st == "NotSigned":
            imza = "İmzasız"
        elif st in ("HashMismatch", "NotTrusted"):
            imza = "İmza GEÇERSİZ (dosya imzalandıktan sonra değiştirilmiş ya da sahte imza)"
        else:
            imza = "İmza doğrulanamadı"
        seviye = "yüksek" if (c["strong"] and not valid) or st in ("HashMismatch", "NotTrusted") else "orta"
        found.append({"pid": c["pid"], "ad": c["ad"], "yol": c["yol"], "nedenler": c["strong"] + c["weak"],
                      "imza": imza, "seviye": seviye, "ust_surec": c["ust_surec"]})
    found.sort(key=lambda x: (x["seviye"] != "yüksek", x["ad"].lower()))
    _notify(f"Süreç taraması bitti: {len(found)} şüpheli")
    return {"status": "ok", "incelenen_surec": total, "supheli": found,
            "imzali_oldugu_icin_elenen": filtered,
            "ozet": "Şüpheli iz taşıyan süreç bulunmadı." if not found else f"{len(found)} süreç dikkat çekiyor.",
            "not": ("Bunlar kesin zararlı demek değildir, incelemeye değer demektir. Kullanıcıya nedenleri açıkla. "
                    "Kullanıcı İSTERSE stop_process ile (onay sorulur) sonlandırılabilir; başlangıçta da varsa "
                    "remove_startup_program önerilebilir. Kullanıcı istemeden hiçbir süreci kapatma.")}


# ---- 4) Müdahaleler (her biri onay kutusu ister) ----
def stop_process(pid: int, reason: str = ""):
    """Verilen PID'li süreci, kullanıcı onay kutusunda onaylarsa sonlandırır. Windows'un çekirdek süreçleri
    ve FENIX'in kendisi asla sonlandırılmaz. Dosyayı silmez."""
    import psutil
    try:
        pid = int(pid)
    except Exception:
        return {"status": "error", "message": "Geçerli bir süreç numarası (PID) ver."}
    if pid in (0, 4) or pid in (os.getpid(), os.getppid()):
        return {"status": "error", "message": "Bu süreç sonlandırılamaz (sistem ya da FENIX'in kendisi)."}
    try:
        p = psutil.Process(pid)
        name = p.name()
        try:
            exe = p.exe()
        except Exception:
            exe = ""
    except psutil.NoSuchProcess:
        return {"status": "error", "message": "Bu numarada çalışan bir süreç yok (zaten kapanmış olabilir)."}
    except Exception:
        return {"status": "error", "message": "Süreç bilgisi okunamadı."}
    windir = (os.environ.get("WINDIR") or r"C:\Windows").lower()
    if name.lower() in _CRITICAL_NAMES and (not exe or exe.lower().startswith(windir)):
        return {"status": "error",
                "message": f"{name} Windows'un çekirdek bir parçası; kapatılırsa sistem çöker ya da oturum kapanır. "
                           "Bunu sonlandırmıyorum."}
    if not _confirm("Süreç Sonlandırma", f"'{name}' (PID {pid}) sonlandırılsın mı?",
                    f"Yol: {exe or 'bilinmiyor'}\nNeden: {reason or 'kullanıcı isteği'}\n\n"
                    "Bu programın kaydedilmemiş verisi varsa kaybolur. Dosyanın kendisi silinmez."):
        return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    _notify(f"Süreç sonlandırılıyor: {name} ({pid})")
    try:
        p.terminate()
        try:
            p.wait(timeout=5)
        except psutil.TimeoutExpired:
            p.kill()
            p.wait(timeout=5)
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        return {"status": "error",
                "message": ("Bu süreci kapatmak için yönetici yetkisi gerekiyor. Görev Yöneticisi'nden (Ctrl+Shift+Esc) "
                            "sağ tık → Görevi sonlandır ile kapatabilir ya da FENIX'i yönetici olarak açıp tekrar "
                            "deneyebilirsin.")}
    except Exception as e:
        report_error("süreç sonlandırma", e)
        return {"status": "error", "message": GENERIC_ERROR}
    return {"status": "ok", "message": f"{name} (PID {pid}) sonlandırıldı.",
            "not": "Açılışta kendini yeniden başlatıyorsa remove_startup_program ile başlangıçtan da kaldırılabilir."}


def _find_startup(name, entries):
    q = (name or "").strip().lower()
    if not q:
        return []
    exact = [e for e in entries if e["ad"].lower() == q]
    return exact or [e for e in entries if q in e["ad"].lower()]


def remove_startup_program(name: str):
    """Bir programın bilgisayar açılışında otomatik başlamasını, kullanıcı onaylarsa durdurur. Program SİLİNMEZ:
    kayıt değerinin yedeği alınır, Başlangıç klasöründeki kısayol FENIX'in yedek klasörüne taşınır;
    restore_startup_program ile geri alınabilir. 'Tüm kullanıcılar' kayıtları için Windows yönetici onayı çıkar."""
    entries = _startup_entries()
    hits = _find_startup(name, entries)
    if not hits:
        return {"status": "error", "message": f"Başlangıçta '{name}' adında bir girdi bulamadım.",
                "mevcut_girdiler": [e["ad"] for e in entries][:40]}
    if len(hits) > 1:
        return {"status": "error", "message": "Birden fazla eşleşme var; hangisi olduğunu tam adıyla söyle.",
                "eslesenler": [_public_entry(e) for e in hits]}
    e = hits[0]
    where = _SRC_LABEL.get(e["kaynak"], e["kaynak"])
    if not _confirm("Başlangıçtan Kaldır", f"'{e['ad']}' bilgisayar açılışında otomatik başlamasın mı?",
                    f"Nerede: {where}\nKomut: {e['komut'][:300]}\n\nProgram silinmez, sadece açılışta başlamaz. "
                    "Yedeği alınır; istersen geri yüklenebilir."):
        return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    _notify(f"Başlangıçtan kaldırılıyor: {e['ad']}")
    backup = {"ad": e["ad"], "komut": e["komut"], "kaynak": e["kaynak"], "anahtar": e.get("anahtar"),
              "tur": e.get("tur"), "kaldirilma": _dtm.datetime.now().isoformat(timespec="seconds")}

    if e["kaynak"] in ("HKCU", "HKLM"):
        ok, msg = False, ""
        try:
            import winreg
            hive = winreg.HKEY_CURRENT_USER if e["kaynak"] == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            with winreg.OpenKey(hive, e["anahtar"], 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, e["ad"])
            ok = True
        except PermissionError:
            if e["kaynak"] == "HKLM":
                ok, msg = _run_elevated(f"Remove-ItemProperty -LiteralPath {_psq('HKLM:' + chr(92) + e['anahtar'])} "
                                        f"-Name {_psq(e['ad'])}")
            else:
                msg = "Kayıt defterine yazma izni reddedildi."
        except FileNotFoundError:
            msg = "Bu girdi artık yok (başka bir şey kaldırmış olabilir)."
        except Exception as ex:
            report_error("başlangıçtan kaldırma", ex)
            msg = "Kayıt değeri silinemedi."
        if not ok:
            return {"status": "error", "message": msg or "Kaldırılamadı."}
    else:
        os.makedirs(_STARTUP_QUARANTINE_DIR, exist_ok=True)
        dest = os.path.abspath(os.path.join(_STARTUP_QUARANTINE_DIR,
                                            f"{_dtm.datetime.now():%Y%m%d_%H%M%S}_{e['ad']}"))
        try:
            _shutil.move(e["yol"], dest)
        except PermissionError:
            ok, msg = _run_elevated(f"Move-Item -LiteralPath {_psq(e['yol'])} -Destination {_psq(dest)}")
            if not ok:
                return {"status": "error", "message": msg}
        except Exception as ex:
            report_error("başlangıçtan kaldırma", ex)
            return {"status": "error", "message": "Kısayol taşınamadı."}
        backup.update({"yol": e["yol"], "yedek_yol": dest})

    with _SEC_LOCK:
        backups = _load_json(_STARTUP_BACKUP_PATH, [])
        backups = backups if isinstance(backups, list) else []
        backups.append(backup)
        _save_json(_STARTUP_BACKUP_PATH, backups)
        base = _load_json(_STARTUP_BASELINE_PATH, None)
        if isinstance(base, dict) and isinstance(base.get("kayitlar"), dict):
            # Tabandan da çıkar: aynı şey kendini yeniden eklerse "yeni" olarak yakalansın
            base["kayitlar"].pop(startup_entry_key(e), None)
            _save_json(_STARTUP_BASELINE_PATH, base)
    return {"status": "ok", "message": f"'{e['ad']}' artık açılışta başlamayacak. Yedeği alındı.",
            "not": ("Şu an çalışan bir kopyası varsa hâlâ açık olabilir (stop_process ile kapatılabilir). "
                    "Geri almak için restore_startup_program.")}


def restore_startup_program(name: str = ""):
    """remove_startup_program ile kaldırılmış bir başlangıç girdisini, kullanıcı onaylarsa geri yükler.
    name boşsa yedekteki girdileri listeler."""
    backups = _load_json(_STARTUP_BACKUP_PATH, [])
    backups = backups if isinstance(backups, list) else []
    if not name:
        return {"status": "ok", "yedekler": [{"ad": b["ad"], "kaldirilma": b.get("kaldirilma")} for b in backups]}
    q = name.strip().lower()
    idx = [i for i, b in enumerate(backups) if b.get("ad", "").lower() == q] or \
          [i for i, b in enumerate(backups) if q in b.get("ad", "").lower()]
    if not idx:
        return {"status": "error", "message": f"Yedekte '{name}' yok.",
                "yedekler": [b["ad"] for b in backups]}
    i = idx[-1]
    b = backups[i]
    if not _confirm("Başlangıca Geri Ekle", f"'{b['ad']}' yeniden açılışta otomatik başlasın mı?",
                    f"Komut: {b['komut'][:300]}"):
        return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    if b["kaynak"] in ("HKCU", "HKLM"):
        ok, msg = False, ""
        try:
            import winreg
            hive = winreg.HKEY_CURRENT_USER if b["kaynak"] == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            with winreg.CreateKeyEx(hive, b["anahtar"], 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, b["ad"], 0, b.get("tur") or winreg.REG_SZ, b["komut"])
            ok = True
        except PermissionError:
            if b["kaynak"] == "HKLM":
                ptype = "ExpandString" if b.get("tur") == 2 else "String"
                ok, msg = _run_elevated(
                    f"New-ItemProperty -LiteralPath {_psq('HKLM:' + chr(92) + b['anahtar'])} -Name {_psq(b['ad'])} "
                    f"-Value {_psq(b['komut'])} -PropertyType {ptype} -Force | Out-Null")
            else:
                msg = "Kayıt defterine yazma izni reddedildi."
        except Exception as ex:
            report_error("başlangıç geri yükleme", ex)
            msg = "Geri yüklenemedi."
        if not ok:
            return {"status": "error", "message": msg}
    else:
        try:
            _shutil.move(b["yedek_yol"], b["yol"])
        except PermissionError:
            ok, msg = _run_elevated(f"Move-Item -LiteralPath {_psq(b['yedek_yol'])} -Destination {_psq(b['yol'])}")
            if not ok:
                return {"status": "error", "message": msg}
        except Exception as ex:
            report_error("başlangıç geri yükleme", ex)
            return {"status": "error", "message": "Kısayol geri taşınamadı."}
    with _SEC_LOCK:
        backups.pop(i)
        _save_json(_STARTUP_BACKUP_PATH, backups)
        base = _load_json(_STARTUP_BASELINE_PATH, None)
        if isinstance(base, dict) and isinstance(base.get("kayitlar"), dict):
            base["kayitlar"][startup_entry_key(b)] = (b["komut"] if b["kaynak"] in ("HKCU", "HKLM")
                                                      else f"(Başlangıç klasöründe dosya) {b['ad']}")
            _save_json(_STARTUP_BASELINE_PATH, base)
    _notify(f"Başlangıca geri eklendi: {b['ad']}")
    return {"status": "ok", "message": f"'{b['ad']}' yeniden açılışta başlayacak."}


def enable_protection(target: str):
    """Kapalı olan Defender gerçek zamanlı korumasını ve/veya güvenlik duvarını, kullanıcı onaylarsa AÇAR
    (sadece açar, hiçbir korumayı kapatmaz). FENIX onayından sonra Windows'un yönetici onayı (UAC) çıkar.
    Sonunda durumu yeniden okuyup gerçekten açıldı mı söyler."""
    t = (target or "").lower()
    every = any(w in t for w in ("hepsi", "tüm", "tum", "ikisi", "all"))
    want_def = every or any(w in t for w in ("defender", "antivir", "virüs", "virus", "gerçek", "gercek"))
    want_fw = every or any(w in t for w in ("duvar", "firewall"))
    if not (want_def or want_fw):
        return {"status": "error", "message": "Hedef 'defender', 'firewall' ya da 'hepsi' olmalı."}
    if os.name != "nt":
        return {"status": "error", "message": "Bu işlem yalnızca Windows'ta yapılabilir."}
    sonuc = {}
    if want_def:
        others = _other_antivirus()
        if others:
            want_def = False
            sonuc["defender"] = (f"Koruma zaten {', '.join(others)} tarafından sağlanıyor; iki antivirüs aynı anda "
                                 "çalışmaz, Defender'a dokunulmadı.")
    steps = []
    if want_def:
        steps.append(("Defender gerçek zamanlı koruma", "Set-MpPreference -DisableRealtimeMonitoring $false"))
    if want_fw:
        steps.append(("Güvenlik duvarı (tüm ağ türleri)",
                      "Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled True"))
    if not steps:
        return {"status": "ok", **sonuc}
    if not _confirm("Korumayı Aç", "Şunlar açılsın mı?\n" + "\n".join(f"• {s[0]}" for s in steps),
                    "Ardından Windows kendi yönetici onay penceresini (UAC) gösterecek."):
        return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    _notify("Koruma açılıyor: " + ", ".join(s[0] for s in steps))
    ok, msg = _run_elevated("; ".join(s[1] for s in steps))
    if want_def:
        mp = _ps_json(_MP_QUERY)
        on = isinstance(mp, dict) and mp.get("RealTimeProtectionEnabled") is True
        sonuc["defender"] = "açık" if on else f"hâlâ kapalı. Elle açmak için: {_HOWTO['defender']}"
    if want_fw:
        fw = [p for p in _as_list(_ps_json(_FW_QUERY)) if isinstance(p, dict)]
        off = [_FW_NAMES.get(p.get("Name"), p.get("Name")) for p in fw if p.get("On") != "True"]
        sonuc["guvenlik_duvari"] = ("tüm ağ türlerinde açık" if fw and not off else
                                    f"hâlâ kapalı ({', '.join(off) or 'okunamadı'}). Elle açmak için: {_HOWTO['firewall']}")
    out = {"status": "ok" if ok else "error", **sonuc}
    if msg:
        out["message"] = msg
    return out


# ---------------- rapor dışa aktarma ----------------
_REPORTS = None        # app tarafından verilir (ReportStore)


def set_report_store(store):
    global _REPORTS
    _REPORTS = store


def export_report(query: str = "", format: str = "docx"):
    """Raporlarım'daki bir raporu Word (.docx) ya da PDF dosyası olarak dışa aktarır. query boşsa en son
    raporu, doluysa başlığında o metin geçen en yeni raporu alır."""
    if not _REPORTS:
        return {"status": "error", "message": "Rapor deposu hazır değil."}
    fmt = "pdf" if "pdf" in (format or "").lower() else "docx"
    items = _REPORTS.list(query.strip() if query else "")
    if not items:
        return {"status": "error", "message": "Eşleşen rapor bulunamadı." if query else "Henüz rapor yok."}
    item = items[0]
    _notify(f"Dışa aktarılıyor ({fmt}): {item['title'][:40]}")
    try:
        out_path = _REPORTS.export(item["path"], fmt)
    except Exception as e:
        report_error("rapor dışa aktarma", e)
        return {"status": "error", "message": GENERIC_ERROR}
    return {"status": "ok", "baslik": item["title"], "bicim": fmt, "yol": out_path}


# ---------------- unutma ----------------
def forget(text: str):
    """Hafızadan (konuşmalar, notlar, anlamsal hafıza) içinde verilen metin geçen kayıtları siler. Onay ister."""
    if not _MEMORY:
        return {"status": "error", "message": "Hafıza hazır değil."}
    text = (text or "").strip()
    if len(text) < 3:
        return {"status": "error", "message": "Ne unutulacağını en az 3 harfle belirt."}
    n_msgs, n_notes = _MEMORY.count_matching(text)
    if not (n_msgs or n_notes):
        return {"status": "ok", "message": "Hafızada bununla ilgili kayıt bulunamadı."}
    if not _confirm("Hafızadan silinecek", f"'{text}' geçen {n_msgs} mesaj ve {n_notes} not silinsin mi?",
                    "Bu işlem geri alınamaz."):
        return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    _MEMORY.forget_matching(text)
    _notify(f"Hafızadan silindi: '{text}' ({n_msgs} mesaj, {n_notes} not)")
    return {"status": "ok", "silinen_mesaj": n_msgs, "silinen_not": n_notes}


NEW_SCHEMAS = [
    {"name": "find_files",
     "description": ("Bilgisayarda dosya arar (Masaüstü/Belgeler/İndirilenler, OneDrive dahil). Ad parçası, *.py gibi "
                     "kalıp, uzantı ya da dosya İÇİNDE geçen metinle arar. Kod ve ödev dosyalarını bulmak için kullan."),
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "Ad parçası ya da kalıp (ör. 'ödev', '*.py')"},
         "folder": {"type": "string", "description": "masaüstü, belgeler, indirilenler, ev ya da klasör adı/yolu"},
         "content": {"type": "string", "description": "Dosya içinde aranacak metin (isteğe bağlı)"},
         "extension": {"type": "string", "description": "Uzantı (ör. .py, .docx)"}}}},
    {"name": "list_folder",
     "description": "Bir klasörün içindekileri listeler (masaüstü, belgeler, 'masaüstü/fenix' ya da tam yol).",
     "parameters": {"type": "object", "properties": {"folder": {"type": "string"}}}},
    {"name": "read_file",
     "description": ("Bir dosyayı okur: kod, metin, PDF, Word, Excel, resim. Kodu incelemek, hatayı bulmak, ödevi "
                     "özetlemek için. Dosyanın yerini bilmiyorsan önce find_files kullan."),
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Tam yol ya da 'masaüstü/klasör/dosya.py'"},
         "question": {"type": "string", "description": "Resimse özellikle neye bakılacağı"},
         "find": {"type": "string", "description": "Büyük dosyada aranacak metin (ör. 'footer'); sadece geçtiği yerler döner"},
         "start_line": {"type": "integer", "description": "Okunacak ilk satır (içindekiler listesindeki numaralar)"},
         "end_line": {"type": "integer", "description": "Okunacak son satır"}}, "required": ["path"]}},
    {"name": "edit_file",
     "description": ("Metin/kod dosyasında BİR parçayı değiştirir ya da siler (new_text boşsa). Büyük dosyada küçük bir "
                     "düzeltme için bunu kullan, bütün dosyayı write_file ile yeniden yazma. old_text, read_file "
                     "çıktısındaki metnin satır numarası olmadan birebir aynısı olmalı ve dosyada bir kez geçmeli. "
                     "Onay sorulur, önce yedek alınır."),
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string"},
         "old_text": {"type": "string", "description": "Değişecek/silinecek metin (birebir)"},
         "new_text": {"type": "string", "description": "Yerine gelecek metin; silmek için boş bırak"},
         "reason": {"type": "string", "description": "Kısa açıklama (onay kutusunda görünür)"}},
         "required": ["path", "old_text"]}},
    {"name": "write_file",
     "description": ("Yeni dosya oluşturur ve içine yazar (kod, not, ödev taslağı). Varsayılan yer Masaüstü. Var olan "
                     "dosyanın üzerine yazmak için overwrite=true gerekir ve kullanıcıdan onay istenir. WORD ve PDF "
                     "belgesi de oluşturur: yol .docx ya da .pdf ile bitsin, content Markdown olsun (# başlık, - madde, "
                     "| tablo |, **kalın**); program onu gerçek Word/PDF belgesine çevirir."),
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Dosya adı ya da yol (ör. 'masaüstü/odev/rapor.md')"},
         "content": {"type": "string"}, "overwrite": {"type": "boolean"}}, "required": ["path", "content"]}},
    {"name": "set_voice",
     "description": ("FENIX'in KENDİ konuşma sesini ayarlar: hız (rate), ton (pitch), ses yüksekliği (volume). "
                     "'daha yavaş konuş' -> rate '-15%', 'daha hızlı' -> '+15%', 'daha kalın ses' -> pitch '-8Hz', "
                     "'daha ince' -> '+8Hz', 'daha yüksek sesle oku' -> volume '+20%'. Değerler mutlak; mevcut değer "
                     "sonuçta döner. Bilgisayarın genel sesi için set_system_volume kullan."),
     "parameters": {"type": "object", "properties": {
         "rate": {"type": "string"}, "pitch": {"type": "string"}, "volume": {"type": "string"},
         "reset": {"type": "boolean", "description": "Varsayılana dön"}}}},
    {"name": "set_reminder",
     "description": ("Hatırlatma kurar. 'when' için sistemdeki ŞU ANKİ TARİH/SAATE göre hesaplanmış "
                     "'YYYY-AA-GG SS:DD' ver (ya da '20 dakika sonra', 'yarın 15:00' gibi Türkçe ifade)."),
     "parameters": {"type": "object", "properties": {
         "when": {"type": "string"}, "text": {"type": "string", "description": "Neyin hatırlatılacağı"}},
         "required": ["when", "text"]}},
    {"name": "list_reminders", "description": "Bekleyen hatırlatmaları listeler.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "cancel_reminder", "description": "Numarası verilen hatırlatmayı iptal eder.",
     "parameters": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}},
    {"name": "save_shortcut",
     "description": ("Kısayol komutu kaydeder: tek cümleyle birden çok iş. Ör. kullanıcı 'çalışma modu dediğimde VS "
                     "Code'u, Spotify'ı ve proje klasörünü aç' derse name='çalışma modu', steps=['VS Code'u aç', "
                     "'Spotify'ı aç', 'masaüstündeki proje klasörünü aç']. Her adım FENIX'e verilecek kısa bir komut."),
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string"}, "steps": {"type": "array", "items": {"type": "string"}}},
         "required": ["name", "steps"]}},
    {"name": "list_shortcuts", "description": "Kayıtlı kısayol komutlarını listeler.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "delete_shortcut", "description": "Kısayol komutunu siler.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "forget",
     "description": ("Kullanıcı 'bunu unut', 'şunu hafızandan sil' derse: içinde verilen metin geçen konuşma ve notları "
                     "kalıcı hafızadan siler (onay sorulur)."),
     "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "inspect_system",
     "description": ("KENDİ bilgisayarının anlık röntgenini çeker: en çok CPU/RAM kullanan süreçler, başlangıçta "
                     "otomatik açılan programlar, bilgisayarda dinleyen (LISTEN) yerel portlar, disk doluluğu. "
                     "'Bilgisayarımda neler çalışıyor', 'gereksiz başlangıç programı var mı', 'kaynak tüketen ne', "
                     "'performans neden düşük' gibi isteklerde kullan. Sadece OKUR, hiçbir şeyi kapatmaz/silmez."),
     "parameters": {"type": "object", "properties": {
         "focus": {"type": "string", "description": "İsteğe bağlı odak: 'süreç', 'port', 'başlangıç', 'disk'"}}}},
    {"name": "inspect_website_security",
     "description": ("Bir web sitesi için PASİF güvenlik/durum gözlemleri çıkarır: TLS/sertifika süresi, DNS/alan "
                     "adı kaydı, robots.txt/sitemap, teknoloji parmak izi, eksik güvenlik başlıkları, bilinen "
                     "hassas dosya yollarının (.env, .git/config, yedek dosyaları) açıkta olup olmadığı, "
                     "script dosyalarında unutulmuş anahtar KALIBI (değer ASLA döndürülmez, sadece 'bulundu/"
                     "bulunmadı'). Kullanıcı bir siteyi/sunucuyu (kendisinin ya da izinli denetlediği bir "
                     "müşterinin) 'incele', 'denetle', 'güvenlik açısından bak' derse kullan. Sadece herkese "
                     "açık GET isteğiyle okunabilen bilgidir; şifre denemez, zafiyet/sızma denemesi YAPMAZ, "
                     "bulunan dosyaların İÇERİĞİNİ okumaz - amaç site sahibini eksikler konusunda bilgilendirmektir."),
     "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "check_project_security",
     "description": ("KENDİ proje klasörünü (yayına çıkmadan / GitHub'a göndermeden önce) kontrol eder: .env "
                     "dosyaları .gitignore'a eklenmiş mi, kod içinde unutulmuş API anahtarı/şifre KALIBI var mı "
                     "(değer gösterilmez, sadece dosya+satır numarası), .git deposu var mı. Kullanıcı 'bunu "
                     "yayınlamadan önce kontrol et', 'projemde açık kalmış bir şey var mı' derse kullan. "
                     "Sadece kullanıcının KENDİ diskindeki dosyaları okur, dışarıya hiçbir şey göndermez."),
     "parameters": {"type": "object", "properties": {
         "folder": {"type": "string", "description": "Proje klasörü (ör. 'masaüstü/fenix')"}}}},
    {"name": "export_report",
     "description": ("Raporlarım'daki bir raporu Word (.docx) ya da PDF dosyası olarak dışa aktarır. Kullanıcı "
                     "'bu raporu Word yap', 'PDF olarak kaydet', 'raporu dışa aktar' derse kullan."),
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Raporun başlığında geçen bir kelime (boşsa en son rapor)"},
         "format": {"type": "string", "enum": ["docx", "pdf"], "description": "docx (Word) ya da pdf"}}}},
]


# Güvenli modda da verilen, sisteme dokunmayan araçlar (okuma, hatırlatma, ses ayarı, kısayol kaydı)
READONLY_FUNCTIONS = {"look_at_screen", "read_webpage", "search_web", "find_files", "list_folder", "read_file",
                      "set_voice", "set_reminder", "list_reminders", "cancel_reminder", "save_shortcut",
                      "list_shortcuts", "delete_shortcut", "forget", "inspect_system", "inspect_website_security",
                      "export_report", "check_project_security", "check_windows_security", "watch_startup_programs",
                      "find_suspicious_processes", "network_connections", "check_link", "cookie_guard", "scan_project",}

WHITELISTED_FUNCTIONS = {
    "network_connections": sec.network_connections,
    "check_link": sec.check_link,
    "cookie_guard": sec.cookie_guard,
    "scan_project": sec.scan_project,
    "run_command": run_command,
    "open_app_by_name": open_app_by_name,
    "open_url": open_url,
    "look_at_screen": look_at_screen,
    "read_webpage": read_webpage,
    "search_web": search_web,
    "open_folder_by_name": open_folder_by_name,
    "set_system_volume": set_system_volume,
    "find_files": find_files,
    "list_folder": list_folder,
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "set_voice": set_voice,
    "set_reminder": set_reminder,
    "list_reminders": list_reminders,
    "cancel_reminder": cancel_reminder,
    "save_shortcut": save_shortcut,
    "list_shortcuts": list_shortcuts,
    "delete_shortcut": delete_shortcut,
    "forget": forget,
    "inspect_system": inspect_system,
    "inspect_website_security": inspect_website_security,
    "export_report": export_report,
    "check_project_security": check_project_security,
    "check_windows_security": check_windows_security,
    "watch_startup_programs": watch_startup_programs,
    "find_suspicious_processes": find_suspicious_processes,
    "stop_process": stop_process,
    "remove_startup_program": remove_startup_program,
    "restore_startup_program": restore_startup_program,
    "enable_protection": enable_protection,
}

FUNCTION_SCHEMAS = [
    {
        "name": "run_command",
        "description": "Windows PowerShell komutu çalıştırır. Diğer fonksiyonların karşılamadığı her sistem işlemi için. Riskli komutlarda otomatik onay istenir.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "PowerShell komutu"},
            "description": {"type": "string", "description": "Kısa Türkçe açıklama"},
        }, "required": ["command", "description"]},
    },
    {
        "name": "open_app_by_name",
        "description": "Uygulama/oyun ismiyle açar.",
        "parameters": {"type": "object", "properties": {
            "app_name": {"type": "string", "description": "Uygulama adı"}}, "required": ["app_name"]},
    },
    {
        "name": "open_url",
        "description": ("Web sitesini kullanıcının tarayıcısında AÇAR. Yalnızca kullanıcı açılmasını açıkça "
                        "istediğinde kullan (örn. 'Opera'dan YouTube'u aç'). Araştırma/analiz/inceleme için "
                        "ASLA kullanma; onun yerine read_webpage kullan. Dakikada en fazla 3 sekme açılır."),
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"}, "browser_name": {"type": "string"}}, "required": ["url"]},
    },
    {
        "name": "look_at_screen",
        "description": ("Kullanıcının bilgisayar ekranına o an bakar ve ekranda ne olduğunu (açık pencereler, yazılar, "
                        "hata mesajları, kod, oyun vb.) ayrıntılı tarif eder. Kullanıcı ekranından, 'buradan', 'bu "
                        "hata', 'bunu gör' gibi bir şeyden bahsederse ya da ekranı görmen gerekirse MUTLAKA bunu çağır; "
                        "asla 'ekranını göremiyorum' deme."),
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string", "description": "Ekranda özellikle neye bakılacağı (isteğe bağlı)"}}},
    },
    {
        "name": "read_webpage",
        "description": ("Bir sayfayı tarayıcı AÇMADAN arka planda okur: başlık, metin ve aynı siteye giden linkleri döner. "
                        "Araştırma, analiz ve bilgi toplama için bunu kullan; gerekirse dönen linklerden devam et."),
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
    {
        "name": "search_web",
        "description": "Web'de arama yapar (tarayıcı açmadan). Başlık, link ve özet listesi döner; sonra read_webpage ile oku.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "open_folder_by_name",
        "description": "Klasörü isme göre bulup açar (varsayılan Masaüstü).",
        "parameters": {"type": "object", "properties": {
            "folder_name": {"type": "string"}, "base_dir": {"type": "string"}}, "required": ["folder_name"]},
    },
    {
        "name": "set_system_volume",
        "description": "Sistem sesini 0-100 ayarlar.",
        "parameters": {"type": "object", "properties": {
            "level": {"type": "integer"}}, "required": ["level"]},
    },
    {
        "name": "check_windows_security",
        "description": ("Bilgisayarın temel korumalarını OKUR: antivirüs/Defender gerçek zamanlı koruma ve tanım yaşı, "
                        "kurcalama koruması, güvenlik duvarı (her ağ türü), SmartScreen, UAC, son Windows güncellemesi. "
                        "Kapalı/eski olanlar için nasıl açılacağını döner. 'Bilgisayarımın güvenliği nasıl', 'korumam açık "
                        "mı', 'Defender çalışıyor mu' gibi isteklerde kullan. Hiçbir ayarı değiştirmez."),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "watch_startup_programs",
        "description": ("Açılışta otomatik başlayan programları (kayıt defteri Run/RunOnce + Başlangıç klasörleri) diskte "
                        "saklanan tabanla karşılaştırır; yeni eklenen ya da komutu değiştirilen girdileri bildirir "
                        "(zararlı yazılımlar kendini genelde buraya ekler). Kullanıcı yeni girdileri KENDİSİNİN "
                        "kurduğunu söylerse ya da 'başlangıç değişikliklerini onayla' derse accept_current=true ver."),
        "parameters": {"type": "object", "properties": {
            "accept_current": {"type": "boolean",
                               "description": "Sadece kullanıcı değişiklikleri kendisinin yaptığını açıkça söylediyse true"}}},
    },
    {
        "name": "find_suspicious_processes",
        "description": ("Çalışan süreçlerde zararlı yazılım izlerini arar: sistem dosyası adını taşıyıp Windows klasörü "
                        "dışından çalışanlar, sistem adını taklit eden isimler (svch0st.exe gibi), Temp/İndirilenler/"
                        "Public/AppData kökünden çalışanlar, dosyası silinmiş halde çalışanlar; adayların Windows imzasını "
                        "doğrular. 'Bilgisayarımda virüs var mı', 'şüpheli bir şey çalışıyor mu', 'hacklendim mi' gibi "
                        "isteklerde kullan. Sadece okur, hiçbir şeyi kapatmaz."),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "stop_process",
        "description": ("Verilen PID'li süreci sonlandırır; kullanıcıya onay kutusu gösterilir. Windows çekirdek süreçleri "
                        "reddedilir. SADECE kullanıcı açıkça kapatılmasını istediğinde çağır, bulgu üzerine kendiliğinden "
                        "çağırma."),
        "parameters": {"type": "object", "properties": {
            "pid": {"type": "integer", "description": "Süreç numarası (find_suspicious_processes / inspect_system çıktısından)"},
            "reason": {"type": "string", "description": "Neden kapatıldığı (onay kutusunda gösterilir)"}},
            "required": ["pid"]},
    },
    {
        "name": "remove_startup_program",
        "description": ("Bir programın açılışta otomatik başlamasını durdurur; onay kutusu gösterilir. Program silinmez, "
                        "yedeği alınır ve restore_startup_program ile geri alınabilir. SADECE kullanıcı açıkça "
                        "'başlangıçtan kaldır' dediğinde çağır."),
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Başlangıç girdisinin adı (watch_startup_programs çıktısındaki 'ad')"}},
            "required": ["name"]},
    },
    {
        "name": "restore_startup_program",
        "description": ("remove_startup_program ile kaldırılmış bir girdiyi geri yükler (onay sorulur). name boş verilirse "
                        "yedekteki girdileri listeler."),
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}},
    },
    {
        "name": "enable_protection",
        "description": ("Kapalı olan Defender gerçek zamanlı korumasını ve/veya güvenlik duvarını AÇAR (asla kapatmaz). "
                        "Önce FENIX onay kutusu, sonra Windows yönetici onayı (UAC) çıkar; sonunda gerçekten açıldı mı "
                        "kontrol eder. SADECE kullanıcı 'aç' dediğinde çağır."),
        "parameters": {"type": "object", "properties": {
            "target": {"type": "string", "enum": ["defender", "firewall", "hepsi"]}}, "required": ["target"]},
    },
    {"name": "network_connections",
     "description": ("Şu an internete hangi program hangi adrese bağlı, listeler. İmzası doğrulanamayan programları "
                     "'tanımıyorsan kontrol et' diye işaretler; bu suçlama değildir, normal programlar da imzasız olabilir. "
                     "Salt-okur, hiçbir bağlantıyı kesmez. 'internete kim bağlanıyor', 'hangi program ağa çıkıyor' için."),
     "parameters": {"type": "object", "properties": {}}},
    {"name": "check_link",
     "description": ("Bir linki AÇMADAN oltalama açısından denetler: yönlendirme zinciri, alan adı yaşı, sahte/benzer "
                     "yazım (g00gle gibi), sertifika. Sonuç tahmindir: 'şüpheli' = dikkat et, 'risk bulunmadı' = "
                     "güvenli olduğunun kanıtı DEĞİL. Sonuçtaki 'ozet' alanı hazır, bilgilendirici Türkçe rapordur: "
                     "onu kullanıcıya olduğu gibi aktar (kısaltabilirsin ama 'güvenli' deme, tavsiyeleri koru). "
                     "Sayfa içeriği indirilmez."),
     "parameters": {"type": "object", "properties": {
         "url": {"type": "string", "description": "denetlenecek link"}}, "required": ["url"]}},
    {"name": "cookie_guard",
     "description": ("Hesapların çerezle çalınmasına karşı kontrol listesi verir: tarayıcı eklentileri ve izinleri, "
                     "oturumları kapatma, 2FA, şifre sırası. Çerez içeriğini OKUMAZ. Çerez çalınması otomatik "
                     "tespit edilemez; kullanıcıya bunu açıkça söyle ve listeyi uygulat."),
     "parameters": {"type": "object", "properties": {}}},
    {"name": "scan_project",
     "description": ("Kullanıcının verdiği BİR KLASÖRÜ tarar: açıkta API anahtarı/şifre/private key kalıbı ve "
                     "yayınlanmaması gereken dosyalar (.env, .pem...). Değerleri göstermez, yalnızca dosya+satır verir. "
                     "Kendi FENIX projesi için 'yayınlamadan önce' kontrolü check_project_security'dir; bu araç "
                     "herhangi bir klasör yolu için kullanılır."),
     "parameters": {"type": "object", "properties": {
         "path": {"type": "string", "description": "taranacak klasörün tam yolu"}}, "required": ["path"]}},
]

FUNCTION_SCHEMAS += NEW_SCHEMAS


# v5.9.0: PC araçları (silme, parlaklık, Wi-Fi/Bluetooth, uygulama kapatma, medya, kilit/uyku, pencere, envanter)
# kendi modülünde; import edilince araç tablolarına kayıt olur. En altta olmalı (tablolar tamamlandıktan sonra).
from . import pc_tools as _pc_tools  # noqa: E402,F401
