# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""Eklentiler (MCP) / plugins via the Model Context Protocol.

MCP, yapay zekâ asistanlarının dış araçlara bağlanması için ortak bir standarttır (asistanlar için "USB" gibi).
config.yaml'daki 'eklentiler' listesinde yazan MCP sunucuları FENIX açıldıktan sonra ARKA PLANDA başlatılır; her
sunucunun araçları FENIX'in kendi araçlarının yanına "mcp_<eklenti>_<araç>" adıyla eklenir.

GÜVENLİK:
  • Yalnızca config.yaml'a SENİN yazdığın eklentiler çalışır; FENIX kendiliğinden eklenti indirip kurmaz.
  • Sunucunun "salt okunur" (readOnlyHint) dediği araçlar onaysız çalışır ve Güvenli modda da kullanılabilir.
    Diğer HER araç (yazma, silme, commit, taşıma...) çalışmadan önce onay kutusu açılır. 'onay: her_zaman'
    yazılırsa o eklentinin salt okunur araçları da onay ister.
  • Eklentiler komut hafızasına girmez (her seferinde yapay zekâ ve onay kuralları devrede).
  • 'mcp' paketi kurulu değilse eklentiler sessizce kapalı kalır, FENIX'in geri kalanı etkilenmez.
Kurulum: Eklentileri_Kur.bat (mcp + hazır eklentiler)."""
import asyncio
import json
import os
import re
import shutil
import sys
import threading
import time

from . import functions as fx

PREFIX = "mcp_"
CALL_TIMEOUT = 90           # tek bir araç çağrısının saniye sınırı
START_TIMEOUT = 120         # bir eklentinin başlaması için (npx ilk seferde paketi indirir)
LOG_PATH = os.path.join("data", "eklentiler.log")

# config.yaml'da 'eklentiler' yoksa kullanılan hazır liste. Yer tutucular: {python} {masaustu} {belgeler} {fenix}
VARSAYILAN = [
    {"ad": "zaman", "komut": ["{python}", "-m", "mcp_server_time"],
     "kelimeler": r"saat dilimi|saat kaç|saat kac|kaç saat fark|kac saat fark|zaman dilimi|timezone|tarihte saat"},
    {"ad": "git", "komut": ["{python}", "-m", "mcp_server_git"],
     "kelimeler": r"\bgit\b|commit|branch|\bdal\b|depo|repo|değişiklikler|degisiklikler|diff|staged|checkout"},
    {"ad": "dosyalar", "komut": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "{masaustu}", "{belgeler}"],
     "kelimeler": r"klasör ağacı|klasor agaci|dizin ağacı|dizin agaci|klasör yapısı|klasor yapisi|taşı|tasi|"
                  r"yeniden adlandır|yeniden adlandir|dosya bilgisi|ne zaman değiştirildi"},
]

_LOCK = threading.RLock()
_STATE = {"loop": None, "thread": None, "servers": {}, "mesaj": "", "basladi": False}


# ------------------------------------------------------------------ yardımcılar
def available():
    try:
        from mcp import ClientSession, StdioServerParameters  # noqa: F401
        from mcp.client.stdio import stdio_client  # noqa: F401
        return True
    except Exception:
        return False


def _log(msg):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass


def _python_exe():
    exe = sys.executable or "python"
    if exe.lower().endswith("pythonw.exe"):
        exe = exe[:-len("pythonw.exe")] + "python.exe"
    return exe


def _yer_tutucular():
    home = os.path.expanduser("~")

    def ilk(*adaylar):
        for a in adaylar:
            if os.path.isdir(a):
                return a
        return adaylar[0]
    one = os.environ.get("OneDrive", "")
    return {"python": _python_exe(),
            "masaustu": ilk(os.path.join(home, "Desktop"), os.path.join(one, "Desktop") if one else "",
                            os.path.join(home, "Masaüstü")),
            "belgeler": ilk(os.path.join(home, "Documents"), os.path.join(one, "Documents") if one else "",
                            os.path.join(home, "Belgeler")),
            "fenix": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}


def komut_coz(komut):
    """Ayardaki komutu çalıştırılabilir listeye çevirir: yer tutucular doldurulur, Windows'ta 'npx' -> 'npx.cmd'."""
    if isinstance(komut, str):
        komut = komut.split()
    yt = _yer_tutucular()
    out = []
    for p in komut or []:
        p = str(p)
        if p in ("{masaustu}", "{belgeler}") and not os.path.isdir(yt[p[1:-1]]):
            continue                         # bu bilgisayarda o klasör yoksa eklentiye verilmez (yoksa açılmaz)
        for k, v in yt.items():
            p = p.replace("{" + k + "}", v)
        out.append(p)
    if out:
        yol = shutil.which(out[0])
        if yol:
            out[0] = yol
    return out


def arac_adi(eklenti, arac):
    ad = re.sub(r"[^a-zA-Z0-9_]", "_", f"{PREFIX}{eklenti}_{arac}")
    return ad[:64]


_KEEP = {"type", "description", "properties", "required", "items", "enum"}


def sema_temizle(s):
    """MCP'nin JSON şemasını Groq ve Gemini'nin kabul ettiği sade biçime indirir ($schema, anyOf, default... atılır)."""
    if not isinstance(s, dict):
        return {"type": "string"}
    out = {k: v for k, v in s.items() if k in _KEEP}
    t = out.get("type")
    if isinstance(t, list):                                  # ["string", "null"] -> "string"
        t = next((x for x in t if x != "null"), "string")
    if not t:
        alt = s.get("anyOf") or s.get("oneOf") or []
        alt = [a for a in alt if isinstance(a, dict) and a.get("type") != "null"]
        if alt:
            return sema_temizle(dict(alt[0], description=s.get("description", alt[0].get("description", ""))))
        t = "object" if "properties" in s else "string"
    out["type"] = t
    if "description" in out:
        out["description"] = str(out["description"])[:300]
    if t == "object":
        out["properties"] = {k: sema_temizle(v) for k, v in (s.get("properties") or {}).items()}
        req = [r for r in (s.get("required") or []) if r in out["properties"]]
        if req:
            out["required"] = req
        else:
            out.pop("required", None)
    elif t == "array":
        out["items"] = sema_temizle(s.get("items") or {"type": "string"})
    if "enum" in out and not isinstance(out["enum"], list):
        out.pop("enum")
    return out


def _attr(obj, *names, default=None):
    for n in names:
        if obj is not None and getattr(obj, n, None) is not None:
            return getattr(obj, n)
    return default


def sonuc_metni(res):
    """CallToolResult -> FENIX araç sonucu sözlüğü."""
    parcalar = []
    for c in _attr(res, "content", default=[]) or []:
        txt = getattr(c, "text", None)
        if txt:
            parcalar.append(txt)
        elif getattr(c, "type", "") == "image":
            parcalar.append("(görsel döndü)")
    yapili = _attr(res, "structured_content", "structuredContent")
    if not parcalar and yapili:
        parcalar.append(json.dumps(yapili, ensure_ascii=False))
    metin = "\n".join(parcalar).strip() or "(boş sonuç)"
    if _attr(res, "is_error", "isError", default=False):
        return {"status": "error", "message": metin[:3000]}
    return {"status": "ok", "message": metin[:12000]}


# ------------------------------------------------------------------ sunucu
def ortam_coz(ortam, anahtarlar=None):
    """Eklentiye verilecek ortam değişkenleri. '{anahtar:tavily}' gibi değerler config.yaml'daki api_keys'ten
    doldurulur: anahtarı iki kez yazmak gerekmez ve eklenti satırı paylaşılsa bile anahtar görünmez."""
    anahtarlar = anahtarlar or {}
    out = {}
    for k, v in (ortam or {}).items():
        v = str(v)
        m = re.fullmatch(r"\{anahtar:([\w-]+)\}", v.strip())
        if m:
            v = str(anahtarlar.get(m.group(1)) or "")
        out[str(k)] = v
    return out


class Sunucu:
    def __init__(self, ayar, anahtarlar=None):
        self.ad = re.sub(r"[^a-zA-Z0-9_]", "_", str(ayar.get("ad") or "eklenti"))[:20]
        self.komut = komut_coz(ayar.get("komut"))
        self.ortam = ortam_coz(ayar.get("ortam"), anahtarlar)
        self.onay_her_zaman = str(ayar.get("onay") or "").lower() in ("her_zaman", "always")
        self.kelimeler = ayar.get("kelimeler") or ""
        self.durum = "başlatılıyor"
        self.hata = ""
        self.araclar = {}           # FENIX adı -> (asıl ad, salt_okunur, yikici)
        self.session = None
        self.stop = None

    def ozet(self):
        if self.durum == "hazır":
            return f"{self.ad}: hazır ({len(self.araclar)} araç)"
        return f"{self.ad}: {self.durum}" + (f" — {self.hata}" if self.hata else "")


def _hata_aciklama(srv, e):
    while isinstance(e, BaseExceptionGroup) and e.exceptions:     # asyncio görev grubu: asıl hatayı al
        e = e.exceptions[0]
    t = f"{type(e).__name__}: {e}"
    exe = os.path.basename(srv.komut[0]).lower() if srv.komut else ""
    if isinstance(e, FileNotFoundError) or "No such file" in t or "cannot find" in t.lower():
        if exe.startswith("npx") or exe.startswith("node"):
            return "Node.js bulunamadı (nodejs.org'dan LTS sürümünü kur)"
        return f"program bulunamadı: {srv.komut[0] if srv.komut else '?'}"
    if "mcp_server_git" in " ".join(srv.komut) and not shutil.which("git"):
        return "Git bulunamadı (git-scm.com'dan kur, sonra FENIX'i yeniden aç)"
    if "mcp_server_" in " ".join(srv.komut) and ("No module named" in t or "Connection closed" in t):
        return "eklenti paketi kurulu değil (Eklentileri_Kur.bat'ı çalıştır)"
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return "zamanında başlamadı"
    return t[:200]


async def _calistir(srv):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as e:
        srv.durum, srv.hata = "hata", f"'mcp' paketi yüklenemedi ({type(e).__name__})"
        return
    if not srv.komut:
        srv.durum, srv.hata = "hata", "komut yazılmamış"
        return
    srv.stop = asyncio.Event()
    env = dict(os.environ)
    env.update(srv.ortam)
    params = StdioServerParameters(command=srv.komut[0], args=srv.komut[1:], env=env)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        errlog = open(LOG_PATH, "a", encoding="utf-8", errors="replace")
    except Exception:
        errlog = open(os.devnull, "w")
    try:
        async with stdio_client(params, errlog=errlog) as (r, w):
            async with ClientSession(r, w) as s:
                await asyncio.wait_for(s.initialize(), START_TIMEOUT)
                tools = (await asyncio.wait_for(s.list_tools(), 60)).tools
                srv.session = s
                _kaydet(srv, tools)
                srv.durum = "hazır"
                _log(f"{srv.ad} hazır: {len(srv.araclar)} araç")
                await srv.stop.wait()
    except Exception as e:
        if srv.durum != "kapatıldı":
            srv.durum, srv.hata = "hata", _hata_aciklama(srv, e)
            _log(f"{srv.ad} başlatılamadı: {type(e).__name__}: {e}")
    finally:
        srv.session = None
        _kaldir(srv)
        try:
            errlog.close()
        except Exception:
            pass


def _kaydet(srv, tools):
    """Sunucunun araçlarını FENIX'in araç listesine ekler."""
    from .llm_client import LLMClient
    with _LOCK:
        mevcut = {s["name"] for s in fx.FUNCTION_SCHEMAS}
        for t in tools:
            asil = t.name
            ad = arac_adi(srv.ad, asil)
            if ad in mevcut or ad in fx.WHITELISTED_FUNCTIONS:
                continue
            ann = getattr(t, "annotations", None)
            salt = bool(_attr(ann, "read_only_hint", "readOnlyHint", default=False))
            yikici = bool(_attr(ann, "destructive_hint", "destructiveHint", default=False))
            sema = sema_temizle(_attr(t, "input_schema", "inputSchema", default={}) or {"type": "object"})
            if sema.get("type") != "object":
                sema = {"type": "object", "properties": {}}
            aciklama = f"[Eklenti: {srv.ad}] " + " ".join((t.description or asil).split())
            fx.FUNCTION_SCHEMAS.append({"name": ad, "description": aciklama[:400], "parameters": sema})
            fx.WHITELISTED_FUNCTIONS[ad] = _cagirici(srv, ad, asil)
            if salt and not srv.onay_her_zaman:
                fx.READONLY_FUNCTIONS.add(ad)
            srv.araclar[ad] = (asil, salt, yikici)
        isimler = set(srv.araclar)
        if isimler:
            desen = srv.kelimeler or r"\b" + re.escape(srv.ad) + r"\b"
            desen = rf"(?:{desen})|\beklenti\b|\b{re.escape(srv.ad)}\b"
            LLMClient._TOOL_GROUPS.append((desen, isimler))


def _kaldir(srv):
    from .llm_client import LLMClient
    with _LOCK:
        isimler = set(srv.araclar)
        if not isimler:
            return
        fx.FUNCTION_SCHEMAS[:] = [s for s in fx.FUNCTION_SCHEMAS if s["name"] not in isimler]
        for ad in isimler:
            fx.WHITELISTED_FUNCTIONS.pop(ad, None)
            fx.READONLY_FUNCTIONS.discard(ad)
        LLMClient._TOOL_GROUPS[:] = [g for g in LLMClient._TOOL_GROUPS if g[1] != isimler]
        srv.araclar = {}


def _cagirici(srv, ad, asil):
    def cagir(**args):
        return arac_cagir(srv, ad, asil, args)
    cagir.__name__ = ad
    return cagir


def arac_cagir(srv, ad, asil, args):
    _, salt, yikici = srv.araclar.get(ad, (asil, False, True))
    if srv.session is None or _STATE["loop"] is None:
        return {"status": "error", "message": f"'{srv.ad}' eklentisi şu an çalışmıyor."}
    if not salt or srv.onay_her_zaman:
        detay = json.dumps(args, ensure_ascii=False, indent=1)[:1500]
        baslik = "Eklenti işlemi" + (" (SİLME / DEĞİŞTİRME)" if yikici else "")
        if not fx._confirm(baslik, f"'{srv.ad}' eklentisi şunu yapmak istiyor: {asil}", detay):
            return {"status": "cancelled", "message": "Kullanıcı onaylamadı."}
    fx._notify(f"Eklenti: {srv.ad} → {asil}")
    try:
        fut = asyncio.run_coroutine_threadsafe(srv.session.call_tool(asil, args or {}), _STATE["loop"])
        return sonuc_metni(fut.result(timeout=CALL_TIMEOUT))
    except Exception as e:
        _log(f"{srv.ad}.{asil} hatası: {type(e).__name__}: {e}")
        return {"status": "error", "message": f"Eklenti hatası ({srv.ad}): {type(e).__name__}"}


# ------------------------------------------------------------------ başlat / durdur / durum
# ------------------------------------------------------------------ katalog ve kullanıcı seçimleri
# Eklentiler penceresinde tek tıkla açılıp kapatılabilen hazır eklentiler. 'anahtar': config.yaml api_keys'teki adı.
KATALOG = [
    {"ad": "zaman", "baslik": "Zaman", "aciklama": "Saat dilimi çevirme: 'Tokyo'da saat kaç?'",
     "gerek": ["mcp_server_time"]},
    {"ad": "git", "baslik": "Git", "aciklama": "Projelerinin geçmişi, değişiklikler, commit (yazma işlemleri onaylı)",
     "gerek": ["mcp_server_git", "git"]},
    {"ad": "dosyalar", "baslik": "Dosyalar", "aciklama": "Masaüstü ve Belgeler'de klasör ağacı, taşıma, arama",
     "gerek": ["node"]},
    {"ad": "tarayici", "baslik": "Tarayıcı (Playwright)", "aciklama": "Siteye gir, forma yaz, butona bas; "
     "sayfayı düğme listesiyle okur", "komut": ["npx", "-y", "@playwright/mcp@latest"], "gerek": ["node"],
     "kelimeler": r"tarayıcı|tarayici|siteye gir|sitesine gir|sitede|web sayfasında|forma yaz|butona|tıkla|tikla|"
                  r"youtube|giriş yap|giris yap|sepete"},
    {"ad": "tavily", "baslik": "Tavily", "aciklama": "Web araması ve sayfa içeriği çekme",
     "komut": ["npx", "-y", "tavily-mcp"], "ortam": {"TAVILY_API_KEY": "{anahtar:tavily}"}, "gerek": ["node"],
     "anahtar": "tavily", "anahtar_url": "https://app.tavily.com",
     "kelimeler": r"tavily|derin arama|sayfayı tara|sayfayi tara|siteyi tara|crawl"},
    {"ad": "notion", "baslik": "Notion", "aciklama": "Notion sayfalarını arama, okuma, yazma",
     "komut": ["npx", "-y", "@notionhq/notion-mcp-server"], "ortam": {"NOTION_TOKEN": "{anahtar:notion}"},
     "gerek": ["node"], "anahtar": "notion", "anahtar_url": "https://www.notion.so/profile/integrations",
     "ipucu": "Notion'da görmesini istediğin sayfada ••• → Connections → entegrasyonunu ekle.",
     "kelimeler": r"notion"},
    {"ad": "github", "baslik": "GitHub", "aciklama": "Issue, pull request, depodaki dosyalar",
     "komut": ["{fenix}/eklentiler/github-mcp-server.exe", "stdio"],
     "ortam": {"GITHUB_PERSONAL_ACCESS_TOKEN": "{anahtar:github}"}, "gerek": ["github_exe"],
     "anahtar": "github", "anahtar_url": "https://github.com/settings/tokens",
     "indir_url": "https://github.com/github/github-mcp-server/releases",
     "ipucu": "Releases sayfasından Windows zip'ini indir, içindeki github-mcp-server.exe'yi fenix\\eklentiler "
              "klasörüne koy.",
     "kelimeler": r"github|issue|pull request|\bpr\b|depo|repo"},
]
_VARS = {v["ad"]: v for v in VARSAYILAN}
for _k in KATALOG:
    if _k["ad"] in _VARS:
        _k.setdefault("komut", _VARS[_k["ad"]]["komut"])
        _k.setdefault("kelimeler", _VARS[_k["ad"]]["kelimeler"])
SECIM_PATH = os.path.join("data", "eklentiler.json")       # pencerede yapılan aç/kapa seçimleri (kişisel)


def _secim_dosyasi():
    try:
        with open(SECIM_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _secim_yaz(d):
    os.makedirs(os.path.dirname(SECIM_PATH), exist_ok=True)
    with open(SECIM_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def secimler():
    return {str(k): bool(v) for k, v in (_secim_dosyasi().get("acik") or {}).items()}


def secim_kaydet(acik):
    d = _secim_dosyasi()
    d["acik"] = {k: bool(v) for k, v in acik.items()}
    _secim_yaz(d)


# ------------------------------------------------------------------ kullanıcının kendi eklediği eklentiler
_NPM_RE = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*(@[A-Za-z0-9._-]+)?$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,60}$")


def ozel_eklentiler():
    return [x for x in (_secim_dosyasi().get("ozel") or []) if isinstance(x, dict) and x.get("ad")]


def ozel_ekle(ad, paket, env_adi=""):
    """Kendi eklentin: npm paketi adı (çoğu MCP sunucusu böyle dağıtılır), isteğe bağlı anahtar değişkeni.
    Komut kabuk üzerinden değil, liste olarak çalışır; paket adı ve değişken adı sıkı denetlenir.
    Kendi eklediğin eklentilerin HER işlemi onay ister (salt okunur olsa bile). -> (True, ad) ya da (False, sebep)"""
    ad = re.sub(r"[^a-z0-9_]", "_", (ad or "").strip().lower())[:20].strip("_")
    paket = (paket or "").strip()
    if paket.startswith("npx "):
        paket = paket.split()[-1]
    env_adi = (env_adi or "").strip().upper()
    if not ad:
        return False, "Bir ad yaz (ör. spotify)."
    if _katalog(ad) or any(x["ad"] == ad for x in ozel_eklentiler()):
        return False, f"'{ad}' adı zaten kullanılıyor."
    if not _NPM_RE.match(paket):
        return False, "Paket adı geçersiz. Eklentinin sayfasında 'npx -y ...' satırındaki paket adını yaz."
    if env_adi and not _ENV_RE.match(env_adi):
        return False, "Anahtar değişkeni adı büyük harf ve alt çizgiden oluşmalı (ör. SPOTIFY_TOKEN)."
    e = {"ad": ad, "baslik": ad.replace("_", " ").title(), "aciklama": f"Kendi eklediğin eklenti ({paket})",
         "komut": ["npx", "-y", paket], "gerek": ["node"], "onay": "her_zaman", "ozel": True}
    if env_adi:
        e["ortam"] = {env_adi: "{anahtar:" + ad + "}"}
        e["anahtar"] = ad
    d = _secim_dosyasi()
    d.setdefault("ozel", []).append(e)
    d.setdefault("acik", {})[ad] = True
    _secim_yaz(d)
    return True, ad


def ozel_sil(ad):
    d = _secim_dosyasi()
    d["ozel"] = [x for x in (d.get("ozel") or []) if x.get("ad") != ad]
    (d.get("acik") or {}).pop(ad, None)
    _secim_yaz(d)


def _taban(cfg):
    """config.yaml'daki liste (yoksa hazır üçlü); 'aktif: false' olanlar da döner (pencerede açılabilsinler)."""
    e = (cfg or {}).get("eklentiler")
    if e is None:
        return [dict(x) for x in VARSAYILAN]
    if e is False:
        return []
    return [dict(x) for x in e if isinstance(x, dict) and x.get("ad")]


def _katalog(ad):
    return next((k for k in KATALOG if k["ad"] == ad), None)


def liste(cfg):
    """Penceredeki satırlar: config'teki eklentiler + kataloğun geri kalanı. Her biri 'aktif' bilgisiyle."""
    sec = secimler()
    out, gorulen = [], set()
    for x in _taban(cfg):
        k = _katalog(x["ad"]) or {}
        e = dict(k, **x)
        e["aktif"] = sec.get(e["ad"], x.get("aktif", True) is not False)
        e["kaynak"] = "ayar"
        out.append(e)
        gorulen.add(e["ad"])
    for k in KATALOG:
        if k["ad"] not in gorulen:
            e = dict(k)
            e["aktif"] = sec.get(k["ad"], False)
            e["kaynak"] = "katalog"
            out.append(e)
            gorulen.add(k["ad"])
    for x in ozel_eklentiler():
        if x["ad"] not in gorulen:
            e = dict(x)
            e["aktif"] = sec.get(x["ad"], True)
            e["kaynak"] = "ozel"
            out.append(e)
    return out


def ayarlar(cfg):
    """Çalıştırılacak eklentiler (pencere seçimleri uygulanmış)."""
    if (cfg or {}).get("eklentiler") is False and not any(secimler().values()):
        return []
    out = []
    for e in liste(cfg):
        if e.get("aktif") and e.get("komut"):
            out.append({k: v for k, v in e.items() if k in ("ad", "komut", "ortam", "onay", "kelimeler")})
    return out


def eksikler(e, cfg=None):
    """Bir eklentinin çalışması için eksik olanlar (insan diliyle)."""
    out = []
    if not available():
        out.append("'mcp' paketi kurulu değil")
    for g in e.get("gerek") or []:
        if g == "node" and not shutil.which("npx"):
            out.append("Node.js kurulu değil (nodejs.org, LTS)")
        elif g == "git" and not shutil.which("git"):
            out.append("Git kurulu değil (git-scm.com)")
        elif g == "github_exe" and not os.path.isfile(os.path.join(_yer_tutucular()["fenix"], "eklentiler",
                                                                    "github-mcp-server.exe")):
            out.append("github-mcp-server.exe yok (fenix\\eklentiler klasörüne koy)")
        elif g.startswith("mcp_server_"):
            try:
                import importlib.util
                if importlib.util.find_spec(g) is None:
                    out.append(f"'{g.replace('_', '-')}' paketi kurulu değil")
            except Exception:
                out.append(f"'{g.replace('_', '-')}' paketi kurulu değil")
    ad = e.get("anahtar")
    if ad:
        v = str(((cfg or {}).get("api_keys") or {}).get(ad) or "").strip()
        if not v or v.startswith("BURAYA"):
            out.append("anahtar girilmemiş")
    return out


def sunucu_durumu(ad):
    s = _STATE["servers"].get(ad)
    if not s:
        return None
    return s.ozet().split(": ", 1)[1] if ": " in s.ozet() else s.durum


def paketleri_kur(bildir=None):
    """Eklenti paketlerini (mcp, zaman, git) FENIX'in kendi Python'una kurar. Arka planda çağrılmalı."""
    import subprocess
    req = os.path.join(_yer_tutucular()["fenix"], "requirements-mcp.txt")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        r = subprocess.run([_python_exe(), "-m", "pip", "install", "-q", "-r", req], capture_output=True, text=True,
                           timeout=900, creationflags=flags)
        ok = r.returncode == 0
        msg = "Eklenti paketleri kuruldu." if ok else ("Kurulum başarısız: " + (r.stderr or r.stdout)[-300:])
    except Exception as e:
        ok, msg = False, f"Kurulum başarısız: {e}"
    _log(msg)
    if bildir:
        bildir(ok, msg)
    return ok


def yeniden_baslat(cfg, bildir=None):
    """Eklentileri durdurup güncel seçimlerle yeniden başlatır (FENIX'i kapatmaya gerek yok)."""
    durdur()
    for _ in range(30):
        if _STATE.get("loop") is None:
            break
        time.sleep(0.1)
    with _LOCK:
        _STATE.update(loop=None, thread=None, servers={}, mesaj="", basladi=False)
    baslat(cfg, bildir=bildir)


def baslat(cfg, bildir=None):
    """Eklentileri arka planda başlatır (FENIX penceresi açıldıktan sonra çağrılır). Bekletmez."""
    with _LOCK:
        if _STATE["basladi"]:
            return
        _STATE["basladi"] = True
    liste = ayarlar(cfg)
    if not liste:
        _STATE["mesaj"] = "Eklenti yok (config.yaml: eklentiler)"
        return
    if not available():
        _STATE["mesaj"] = "Eklentiler kapalı: 'mcp' paketi kurulu değil (Eklentileri_Kur.bat)"
        _log(_STATE["mesaj"])
        return
    servers = {}
    for a in liste:
        s = Sunucu(a, (cfg or {}).get("api_keys") or {})
        while s.ad in servers:
            s.ad += "_"
        servers[s.ad] = s
    _STATE["servers"] = servers

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _STATE["loop"] = loop

        async def hepsi():
            gorevler = [asyncio.create_task(_calistir(s)) for s in servers.values()]

            async def haber():
                for _ in range(START_TIMEOUT * 2):
                    if all(s.durum != "başlatılıyor" for s in servers.values()):
                        break
                    await asyncio.sleep(0.5)
                hazir = [s for s in servers.values() if s.durum == "hazır"]
                n = sum(len(s.araclar) for s in hazir)
                _STATE["mesaj"] = f"Eklentiler: {len(hazir)}/{len(servers)} hazır ({n} araç)"
                if bildir:
                    try:
                        bildir(_STATE["mesaj"])
                    except Exception:
                        pass
            await asyncio.gather(haber(), *gorevler, return_exceptions=True)
        try:
            loop.run_until_complete(hepsi())
        except Exception as e:
            _log(f"eklenti döngüsü durdu: {e}")
        finally:
            _STATE["loop"] = None
    t = threading.Thread(target=run, daemon=True, name="fenix-mcp")
    _STATE["thread"] = t
    t.start()


def durdur():
    loop = _STATE.get("loop")
    for s in list(_STATE["servers"].values()):
        s.durum = "kapatıldı"
        if loop and s.stop is not None:
            try:
                loop.call_soon_threadsafe(s.stop.set)
            except Exception:
                pass
    t = _STATE.get("thread")
    if t:
        t.join(timeout=3)


def durum_metni():
    sat = [_STATE["mesaj"] or ("Eklentiler başlatılıyor…" if _STATE["servers"] else "Eklenti yok")]
    for s in _STATE["servers"].values():
        sat.append("  • " + s.ozet())
        for ad, (asil, salt, yikici) in sorted(s.araclar.items()):
            sat.append(f"      - {asil}" + (" (salt okunur)" if salt else " (onay ister)"))
    return "\n".join(sat)


def eklentileri_listele():
    """FENIX aracı: hangi eklentiler çalışıyor, hangi araçları var."""
    return {"status": "ok", "message": durum_metni()}


SCHEMA = {"name": "eklentileri_listele",
          "description": "Kurulu eklentileri (MCP sunucuları), durumlarını ve araçlarını listeler. 'hangi eklentiler var', "
                         "'eklentiler çalışıyor mu' gibi sorularda kullan.",
          "parameters": {"type": "object", "properties": {}}}


def install():
    """'eklentileri_listele' aracını ekler (uygulama açılırken bir kez)."""
    with _LOCK:
        if "eklentileri_listele" in fx.WHITELISTED_FUNCTIONS:
            return
        fx.WHITELISTED_FUNCTIONS["eklentileri_listele"] = eklentileri_listele
        fx.READONLY_FUNCTIONS.add("eklentileri_listele")
        fx.FUNCTION_SCHEMAS.append(SCHEMA)
        try:
            from .llm_client import LLMClient
            LLMClient._TOOL_GROUPS.append((r"eklenti|plugin|\bmcp\b", {"eklentileri_listele"}))
        except Exception:
            pass
