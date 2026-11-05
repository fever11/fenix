# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Güvenlik Merceği (v5.9.2)
-----------------------
Hepsi salt-okur: hiçbir şeyi engellemez, silmez, içerik indirmez.

1) network_connections() : hangi program hangi adrese bağlı + imzasız/tanımsız işaretleme
2) check_link(url)       : oltalama kontrolü (yönlendirme çözümleme, alan adı yaşı,
                           sahte yazım, sertifika) — sayfa çalıştırılmaz/indirilmez
3) cookie_guard()        : çerez İÇERİĞİNİ okumadan hesap güvenliği taraması
4) scan_project(path)    : projede açıkta anahtar/secret/kritik dosya tespiti
"""
import os
import re
import ssl
import json
import socket
import datetime
import ipaddress
import subprocess
import time
from urllib.parse import urlparse, urljoin

# Bilinen yaygın alan adları (sahte yazım kontrolü için; gerekirse genişlet)
# Bilinen siteler ve ne tür bir site oldukları (rapor ve sahte-yazım kontrolü için; gerekirse genişlet)
_BRANDS = {
    "google.com": "arama / e-posta / hesap sitesi", "facebook.com": "sosyal medya", "instagram.com": "sosyal medya",
    "twitter.com": "sosyal medya", "x.com": "sosyal medya", "youtube.com": "video sitesi",
    "microsoft.com": "Microsoft hesap/yazılım sitesi", "apple.com": "Apple hesap/ürün sitesi",
    "amazon.com": "alışveriş sitesi", "netflix.com": "dizi/film hesabı", "whatsapp.com": "mesajlaşma",
    "telegram.org": "mesajlaşma", "discord.com": "sohbet/oyun topluluğu", "github.com": "kod platformu",
    "paypal.com": "ödeme hizmeti", "binance.com": "kripto borsası", "linkedin.com": "iş/sosyal ağ",
    "outlook.com": "e-posta", "yahoo.com": "e-posta/hesap", "hotmail.com": "e-posta",
    # Türkiye
    "ziraatbank.com.tr": "banka", "isbank.com.tr": "banka", "garantibbva.com.tr": "banka", "akbank.com": "banka",
    "yapikredi.com.tr": "banka", "halkbank.com.tr": "banka", "vakifbank.com.tr": "banka",
    "qnbfinansbank.com": "banka", "denizbank.com": "banka", "enpara.com": "banka", "papara.com": "ödeme hizmeti",
    "iyzico.com": "ödeme hizmeti", "trendyol.com": "alışveriş sitesi", "hepsiburada.com": "alışveriş sitesi",
    "sahibinden.com": "ilan sitesi", "yemeksepeti.com": "yemek siparişi", "n11.com": "alışveriş sitesi",
    "ciceksepeti.com": "alışveriş sitesi", "turkcell.com.tr": "operatör", "vodafone.com.tr": "operatör",
    "turktelekom.com.tr": "operatör",
}
_POPULAR = list(_BRANDS)
_STRICT_BRANDS = {d for d, k in _BRANDS.items() if k in ("banka", "ödeme hizmeti", "kripto borsası")}
_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "cutt.ly", "rb.gy", "shorturl.at",
               "t.ly", "lnkd.in", "tr.ee", "s.id", "buff.ly", "rebrand.ly"}

# Bilinen sistem süreçleri (bunları işaretleme)
# (hepsi küçük harf: karşılaştırma name.lower() ile yapılır)
_KNOWN_PROCS = {"system", "svchost.exe", "lsass.exe", "csrss.exe", "wininit.exe",
                "services.exe", "smss.exe", "winlogon.exe", "dwm.exe", "explorer.exe",
                "msedge.exe", "chrome.exe", "firefox.exe", "code.exe", "python.exe", "pythonw.exe"}

_SIG_TTL = 300          # imza sonucu önbellek süresi (sn)
_SIG_MAX = 15           # tek taramada imzası kontrol edilecek en fazla program


# ----------------------------------------------------------------------
def _levenshtein(a, b):
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


_sig_cache = {}   # yol -> (durum, zaman)


def _signature_batch(paths):
    """Birden çok programın Authenticode imza durumunu TEK PowerShell çağrısıyla sorar.
    Dönüş: {yol: 'Signed' | 'Unsigned' | 'Unknown'}. Windows dışında hepsi 'Unknown'."""
    out = {p: "Unknown" for p in paths}
    if os.name != "nt" or not paths:
        return out
    arr = ",".join("'" + p.replace("'", "''") + "'" for p in paths)
    ps = (f"$ErrorActionPreference='SilentlyContinue'; foreach($p in @({arr})) "
          "{ $st=(Get-AuthenticodeSignature -LiteralPath $p).Status; Write-Output (\"$p|$st\") }")
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                             capture_output=True, text=True, timeout=45,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in (res.stdout or "").splitlines():
            if "|" not in line:
                continue
            path, st = line.rsplit("|", 1)
            st = st.strip()
            if path in out:
                out[path] = "Signed" if st == "Valid" else ("Unsigned" if st == "NotSigned" else "Unknown")
    except Exception:
        pass
    return out


def _signature_status(exe_path):
    """Tek program için imza durumu (5 dk önbellekli)."""
    return _signatures([exe_path]).get(exe_path, "Unknown")


def _signatures(paths):
    """Önbelleği kullanarak yalnızca eksik olanları sorar."""
    now = time.time()
    need = [p for p in dict.fromkeys(paths) if not (p in _sig_cache and now - _sig_cache[p][1] < _SIG_TTL)]
    if need:
        for p, st in _signature_batch(need).items():
            _sig_cache[p] = (st, now)
    return {p: _sig_cache.get(p, ("Unknown", now))[0] for p in paths}


# ----------------------------------------------------------------------
# 1) AĞ BAĞLANTILARI
# ----------------------------------------------------------------------
def _is_local_ip(ip):
    try:
        a = ipaddress.ip_address(ip)
        return a.is_loopback or a.is_unspecified
    except ValueError:
        return False


def network_connections():
    """Şu an internete hangi program, hangi adrese bağlı. Salt-okur liste; kimseyi engellemez.
    İmzası doğrulanamayan programlar 'tanımıyorsan kontrol et' diye işaretlenir; bu bir suçlama değildir
    (birçok normal program da imzasız olabilir)."""
    try:
        import psutil
    except ImportError:
        return {"status": "error", "message": "psutil gerekli (pip install psutil)."}

    rows, seen = [], set()
    try:
        conns = psutil.net_connections(kind="inet")
    except Exception as e:      # Windows'ta yetki yoksa bazen hata verir
        return {"status": "error", "message": f"Bağlantı listesi alınamadı: {type(e).__name__}"}
    for c in conns:
        if not c.raddr or c.status != "ESTABLISHED" or _is_local_ip(c.raddr.ip):
            continue
        try:
            p = psutil.Process(c.pid)
            exe, name = (p.exe() or ""), (p.name() or "")
        except Exception:
            exe, name = "", str(c.pid)
        key = (name, c.raddr.ip, c.raddr.port)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"program": name, "yol": exe, "pid": c.pid, "adres": c.raddr.ip,
                     "port": c.raddr.port, "durum": c.status, "isaret": ""})

    # İmza kontrolü: bilinen sistem/tarayıcı süreçleri atlanır, kalanlardan en fazla _SIG_MAX tane sorulur
    check = [r["yol"] for r in rows if r["yol"] and r["program"].lower() not in _KNOWN_PROCS]
    check = list(dict.fromkeys(check))[:_SIG_MAX]
    sigs = _signatures(check) if check else {}
    for r in rows:
        if r["program"].lower() in _KNOWN_PROCS:
            continue
        if not r["yol"]:
            r["isaret"] = "programın yolu okunamadı"
        elif r["yol"] in sigs:
            if sigs[r["yol"]] == "Unsigned":
                r["isaret"] = "imzasız — tanımıyorsan kontrol et"
            elif sigs[r["yol"]] == "Unknown":
                r["isaret"] = "imza doğrulanamadı — tanımıyorsan kontrol et"
        # sınırın dışında kalanlar işaretlenmez (kontrol edilmedi)
    rows.sort(key=lambda r: (not r["isaret"], r["program"].lower()))
    flagged = sum(1 for r in rows if r["isaret"])
    return {"status": "ok", "toplam": len(rows), "isaretli": flagged, "baglantilar": rows[:80],
            "not": ("İşaret bir suçlama değildir: bazı normal programlar da imzasızdır. Tanımadığın bir program "
                    "varsa adını internette ara ya da Görev Yöneticisi'nde yerini aç. En fazla "
                    f"{_SIG_MAX} programın imzası kontrol edilir. Bu araç hiçbir bağlantıyı kesmez.")}


# ----------------------------------------------------------------------
# 2) LİNK / OLTALAMA KONTROLÜ
# ----------------------------------------------------------------------
_TWO_PART = {"co", "com", "org", "net", "gov", "edu", "ac"}
_PHISH_WORDS = ("login", "signin", "secure", "verify", "account", "update", "support", "wallet", "confirm")


def _registrable(host):
    """Kaba 'kayıtlı alan adı': www.mail.example.com -> example.com, a.b.example.co.uk -> example.co.uk."""
    parts = host.split(".")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in _TWO_PART:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _is_private_host(host):
    try:
        a = ipaddress.ip_address(host)
        return a.is_private or a.is_loopback or a.is_link_local or a.is_reserved
    except ValueError:
        return host in ("localhost",) or host.endswith((".local", ".internal", ".lan"))


def _resolve_redirects(url, max_hops=5):
    """Yönlendirme zincirini SADECE HEAD isteğiyle çözer (gövde indirilmez, içerik çalıştırılmaz)."""
    import requests
    chain, cur = [], url
    for _ in range(max_hops):
        host = (urlparse(cur).hostname or "")
        if _is_private_host(host):
            chain.append({"url": cur, "hata": "yerel/özel adres, istek atılmadı"})
            break
        try:
            r = requests.head(cur, allow_redirects=False, timeout=8,
                              headers={"User-Agent": "Mozilla/5.0"})
        except requests.RequestException as e:
            chain.append({"url": cur, "hata": type(e).__name__})
            break
        chain.append({"url": cur, "durum_kodu": r.status_code})
        loc = r.headers.get("Location")
        if r.status_code in (301, 302, 303, 307, 308) and loc:
            cur = urljoin(cur, loc)
        else:
            break
    return chain, cur


def _domain_age_days(domain):
    """RDAP ile alan adı kayıt yaşı (gün). RDAP yoksa None."""
    import requests
    try:
        d = requests.get(f"https://rdap.org/domain/{domain}", timeout=8).json()
        for ev in d.get("events", []):
            if ev.get("eventAction") in ("registration", "registered"):
                reg = datetime.datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00"))
                return (datetime.datetime.now(datetime.timezone.utc) - reg).days
    except Exception:
        return None
    return None


def _cert_info(host, port=443):
    """TLS sertifika özeti (süresi, veren). Sadece el sıkışma; veri alınmaz."""
    try:
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2      # eski, güvensiz TLS 1.0/1.1 kullanılmaz (CodeQL #1/#2)
        with socket.create_connection((host, port), timeout=6) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as s:
                c = s.getpeercert()
        exp = datetime.datetime.strptime(c["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days = (exp - datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)).days
        return {"gecerli_gun": days, "veren": dict(x[0] for x in c["issuer"]).get("organizationName", ""),
                "durum": "gecerli" if days > 0 else "SÜRESİ DOLMUŞ"}
    except Exception:
        return {"durum": "sertifika alınamadı (TLS yok, süresi dolmuş ya da adres kapalı)"}


# Popüler markalara ait, adında marka geçen gerçek alan adları (yanlış alarm vermesin)
_SAFE_DOMAINS = {"amazonaws.com", "googleapis.com", "googleusercontent.com", "googlevideo.com", "gstatic.com",
                 "microsoftonline.com", "microsoft365.com", "office365.com", "azurewebsites.net", "windows.net",
                 "githubusercontent.com", "github.io", "githubassets.com", "fbcdn.net", "cdninstagram.com",
                 "ytimg.com", "withgoogle.com", "googlesyndication.com", "paypalobjects.com", "twimg.com",
                 "whatsapp.net", "telegram.me", "t.me", "discordapp.com", "discord.gg", "linkedin.cn"}
_BAD_TLDS = {"xyz", "top", "click", "site", "online", "icu", "vip", "work", "cyou", "buzz", "cfd", "sbs",
             "rest", "fit", "link", "shop", "live", "info", "monster", "cam", "support"}


def _normalize_lookalike(text):
    return text.replace("0", "o").replace("1", "l").replace("3", "e").replace("5", "s").replace("rn", "m")


def _is_official(root):
    """Popüler sitenin kendisi, ülke uzantılı hali (google.com.tr) ya da bilinen resmi yan alan adı mı."""
    return (root in _SAFE_DOMAINS or any(root == pop or root.startswith(pop + ".") for pop in _POPULAR)
            or any(root.startswith(pop.split(".")[0] + ".") and len(root.split(".")[-1]) == 2 for pop in _POPULAR
                   if len(pop.split(".")[0]) >= 5 and pop not in _STRICT_BRANDS))


def _spoof_matches(root):
    """root: kayıtlı alan adı (örn. g00gle.com). Popüler bir siteye benzeyen ama o olmayan adı döndürür."""
    if _is_official(root):
        return []
    label, _, tld = root.partition(".")
    if len(label) < 5:                      # kısa adlarda benzerlik hep yanlış alarm verir
        return []
    clean = _normalize_lookalike(label)
    out = []
    for pop in _POPULAR:
        brand = pop.split(".")[0]
        if len(brand) < 5:                   # x.com gibi kısa markalar: benzerlik kuralı uygulanmaz
            continue
        if label == brand:
            if tld.split(".")[-1] in _BAD_TLDS:
                out.append(("aynı marka adı, şüpheli uzantı", pop))
            elif pop in _STRICT_BRANDS and root != pop:
                out.append(("aynı marka adı, resmi adres farklı", pop))
        elif _levenshtein(label, brand) <= 1 or (clean != label and _levenshtein(clean, brand) <= 1):
            out.append(("benzer yazım", pop))
        else:
            toks = clean.split("-")
            if (brand in toks and len(toks) > 1) or any(clean in (brand + w, w + brand) for w in _PHISH_WORDS):
                out.append(("marka adı + ek kelime", pop))
    return out[:1]


def _brand_in_subdomain(final_host, root):
    """mail.google.com.evil.com gibi: marka adı alt alanda ama sitenin asıl adı başka."""
    if _is_official(root) or final_host == root:
        return None
    toks = re.split(r"[^a-z0-9]+", _normalize_lookalike(final_host[:-len(root)]))
    for pop in _POPULAR:
        brand = pop.split(".")[0]
        if len(brand) >= 5 and brand in toks:
            return pop
    return None


def check_link(url: str):
    """Bir linki AÇMADAN denetler: yönlendirme zinciri, alan adı yaşı, sahte yazım, sertifika.
    Sonuç kesin hüküm değildir: 'şüpheli' = dikkat et, 'normal görünüyor' = güvenli kanıtı değil."""
    url = (url or "").strip()
    if not url:
        return {"status": "error", "message": "Denetlenecek bir link ver."}
    if not re.match(r"^https?://", url, re.I):
        if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I) and "://" in url:
            return {"status": "error", "message": "Sadece http/https linkleri denetlenir."}
        url = "https://" + url

    risk = []
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if not host:
        return {"status": "error", "message": "Linkteki adres okunamadı."}
    if "@" in parsed.netloc:
        risk.append("adreste '@' var: yazılan ad gerçek adres olmayabilir (kullanıcı-adı hilesi)")
    if _is_private_host(host):
        return {"status": "ok", "karar": "yerel/özel adres: internette denetlenemez", "riskler": [],
                "zincir": [], "son_adres": url, "alan_yasi_gun": None, "sertifika": {},
                "not": "Hiçbir istek atılmadı."}
    if re.fullmatch(r"[0-9.]+|[0-9a-f:]+", host):
        risk.append("adres alan adı değil, doğrudan IP numarası")

    chain, final_url = _resolve_redirects(url)
    final_host = (urlparse(final_url).hostname or host).lower().removeprefix("www.")
    root = _registrable(final_host)

    if "xn--" in final_host or any(ord(ch) > 127 for ch in final_host):
        risk.append("alan adı alfabe taklidi içerebilir (xn-- / ASCII dışı karakter)")

    for kind, pop in _spoof_matches(root):
        risk.append(f"BENZER-İSİM TUZAĞI ({kind}): {pop}")
    sub_brand = _brand_in_subdomain(final_host, root)
    if sub_brand:
        risk.append(f"{sub_brand} adı alt alanda geçiyor ama sitenin asıl adı {root}")
    if (not _is_official(root) and any(w in final_host for w in _PHISH_WORDS)
            and not any("BENZER-İSİM" in r for r in risk) and not sub_brand):
        risk.append("adreste 'login/secure/verify' gibi oltalamada sık kullanılan bir kelime var")

    low_host = final_host.replace("-", "").replace(".", "")
    if ("edevlet" in low_host or "turkiyegov" in low_host) and not final_host.endswith(".gov.tr"):
        risk.append("e-Devlet/devlet adı geçiyor ama adres .gov.tr ile bitmiyor (resmi devlet siteleri .gov.tr kullanır)")

    age = _domain_age_days(root) if not re.fullmatch(r"[0-9.]+", root) else None
    if final_url.startswith("https"):
        cert = _cert_info(final_host)
    else:
        cert = {"durum": "http - şifresiz"}

    if age is not None and age < 180:
        risk.append(f"alan adı çok yeni ({age} gün)")
    if cert.get("gecerli_gun", 999) < 0:
        risk.append("sertifika süresi dolmuş")
    if len(chain) > 3:
        risk.append("uzun yönlendirme zinciri")
    if final_url.startswith("http:"):
        risk.append("şifresiz HTTP")
    unreachable = any("hata" in c for c in chain)
    if unreachable:
        risk.append("adrese ulaşılamadı; kapanmış ya da yazım hatalı/sahte olabilir")

    kind = _site_kind(root, final_host)
    ozet = _summary(url, final_url, final_host, root, chain, kind, age, cert, risk, unreachable)
    return {"status": "ok",
            "karar": ("ŞÜPHELİ — açma, bilgi girme" if risk
                      else "belirgin bir tehdit bulunamadı (güvenli olduğunun kanıtı değil)"),
            "ozet": ozet,
            "site_turu": kind, "riskler": risk, "zincir": chain, "son_adres": final_url,
            "alan_yasi_gun": age, "sertifika": cert,
            "not": "Sayfa içeriği hiç indirilmedi/çalıştırılmadı. Bu bir tahmindir, kesin hüküm değil."}


def _site_kind(root, final_host):
    """Sitenin ne olduğuna dair kaba tahmin (yalnızca adresten)."""
    if root in _BRANDS:
        return _BRANDS[root]
    if final_host.endswith(".gov.tr"):
        return "devlet kurumu (.gov.tr)"
    if final_host.endswith(".edu.tr") or final_host.endswith(".edu"):
        return "eğitim kurumu"
    if root in _SHORTENERS:
        return "link kısaltma servisi"
    if _is_official(root):
        return "tanınmış bir markanın resmi/yardımcı adresi"
    return ""


def _summary(url, final_url, final_host, root, chain, kind, age, cert, risk, unreachable):
    """Kullanıcıya okunacak kısa, bilgilendirici Türkçe rapor. Hep aynı sırada: nereye gidiyor, ne tür site,
    alan/sertifika bilgisi, işaretler, ne yapmalı. Hiçbir zaman 'güvenli' demez."""
    parts = []
    hops = max(0, len(chain) - 1)
    first_host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if hops and first_host != final_host:
        if _registrable(first_host) in _SHORTENERS:
            parts.append(f"Bu bir kısaltılmış link ({first_host}); asıl adresi {final_host}.")
        else:
            parts.append(f"Bu link {hops} yönlendirmeyle {final_host} adresine çıkıyor.")
    else:
        parts.append(f"Bu link doğrudan {final_host} adresine gidiyor." if not unreachable
                     else f"Bu link {final_host} adresine gidiyor ama adrese ulaşılamadı.")
    if kind:
        parts.append(f"Adrese bakılırsa: {kind}.")
    else:
        parts.append("Tanıdığım büyük sitelerden biri değil; hakkında bilgim yok.")
    bits = []
    if age is not None:
        bits.append(f"alan adı {age // 365} yıllık" if age >= 365 else f"alan adı {age} günlük")
    else:
        bits.append("alan adının yaşını öğrenemedim")
    if final_url.startswith("http:"):
        bits.append("bağlantı şifresiz (HTTP)")
    elif cert.get("gecerli_gun") is not None:
        bits.append("sertifikası geçerli" if cert["gecerli_gun"] > 0 else "sertifikasının süresi dolmuş")
    else:
        bits.append("sertifika bilgisi alınamadı")
    txt = ", ".join(bits)
    parts.append(txt[0].upper() + txt[1:] + ".")
    if risk:
        parts.append("Dikkat çeken noktalar: " + "; ".join(risk) + ".")
        parts.append("Bu linke tıklama; açtıysan şifre, kart ya da kod girme, dosya indirme.")
    else:
        parts.append("Belirgin bir tehdit işareti bulamadım.")
        if kind in ("banka", "ödeme hizmeti", "kripto borsası") or "hesap" in kind or "e-posta" in kind:
            parts.append(f"Yine de giriş yaparken adres çubuğunda {root} yazdığından emin ol; "
                         "şifreni ve doğrulama kodunu yalnızca orada gir, linkle gelen sayfaya girme, siteyi kendin yazarak aç.")
        elif kind in ("alışveriş sitesi", "ilan sitesi", "yemek siparişi", "operatör"):
            parts.append("Ödeme ya da kart bilgisi girmeden önce adresin doğru olduğunu ve kilit simgesini kontrol et.")
        elif kind.startswith("devlet"):
            parts.append("Devlet hizmetlerinde giriş için linkle değil, adresi kendin yazarak ya da e-Devlet uygulamasıyla gir.")
        elif not kind:
            parts.append("Tanımadığın bir sitede şifre, kart bilgisi ya da kimlik bilgisi girmeden, dosya indirmeden önce iki kez düşün.")
        else:
            parts.append("Giriş yaparken ya da bilgi verirken adresin doğru olduğundan emin ol.")
    parts.append("Bu bir adres incelemesi; sayfanın içine bakmadım, güvenli olduğunun kanıtı değil.")
    return " ".join(parts)


# ----------------------------------------------------------------------
# 3) ÇEREZ KORUMASI (içerik okumadan)
# ----------------------------------------------------------------------
def _chrome_extensions(profile_dir):
    """Chrome/Edge uzantı listesi (yalnızca ad+izinler, çerez içeriği okunmaz)."""
    out = []
    for prefs in ("Secure Preferences", "Preferences"):
        p = os.path.join(profile_dir, prefs)
        if not os.path.exists(p):
            continue
        try:
            data = json.load(open(p, encoding="utf-8", errors="ignore"))
            for ext_id, meta in (data.get("extensions", {}).get("settings", {}) or {}).items():
                name = (meta.get("manifest", {}) or {}).get("name", ext_id)
                perms = (meta.get("manifest", {}) or {}).get("permissions", [])
                out.append({"id": ext_id, "ad": name, "izinler": perms})
        except Exception:
            pass
        break
    return out


def cookie_guard():
    """Çerez/oturum çalınmasına karşı PRATİK tarama: eklentiler + oturum dosyalarının
    son değişim zamanı (ani/beklenmedik değişiklik = çalma sinyali) + yapılacaklar listesi.
    Hiçbir çerez içeriği okunmaz."""
    home = os.path.expanduser("~")
    findings, exts = [], []

    suspects = []  # aşırı yetkili eklentiler
    for base in (os.path.join(home, "AppData", "Local", "Google", "Chrome", "User Data"),
                 os.path.join(home, "AppData", "Local", "Microsoft", "Edge", "User Data")):
        if not os.path.isdir(base):
            continue
        for prof in os.listdir(base):
            pd = os.path.join(base, prof)
            for e in _chrome_extensions(pd):
                perms = " ".join(e["izinler"])
                if "cookies" in perms or "webRequest" in perms:
                    suspects.append(e)
                if e not in exts:
                    exts.append(e)
            # Oturum/cookie dosyalarının değişim zamanı (içerik OKUNMAZ)
            for db, label in (("Cookies", "çerez veritabanı"), ("Login Data", "kayıtlı girişler")):
                fp = os.path.join(pd, "Network", db) if db == "Cookies" else os.path.join(pd, db)
                if os.path.exists(fp):
                    age_h = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(fp))).total_seconds() / 3600
                    findings.append({"dosya": f"{os.path.basename(base)}\\{prof}\\{db}",
                                     "son_degisim_saat_once": round(age_h, 1),
                                     "not": label})

    risk = []
    if suspects:
        risk.append(f"{len(suspects)} eklentide çerez/istek izni var (reklam engelleyici ve şifre yöneticileri de ister): " +
                    ", ".join(s['ad'] for s in suspects[:5]) + ". Hepsini tanıyor musun? Tanımadığını kaldır.")

    return {"status": "ok",
            "karar": "Çerez çalınması otomatik tespit edilemez; aşağıdaki kontrol listesini uygula",
            "riskler": risk,
            "eklenti_sayisi": len(exts),
            "dosyalar": findings[:30],
            "yapilacaklar": [
                "Tarayıcıda tanımadığın eklentileri kaldır",
                "Google/Hotmail: ayarlar > güvenlik > tüm oturumları kapat (çalınan çerezi boşa çıkarır)",
                "2. adım doğrulamayı (2FA) aç; SMS değil uygulama/anahtar tabanlı kullan",
                "Önemli hesaplarda şifre değiştir (sıra: e-posta > banka > sosyal medya > diğer)",
                "Chrome'da 'eşitleme parolası' açıksa kapat ya da güçlendir",
                "Kırık/crack program indirdiysen o programı kaldır ve bilgisayarı Defender ile tam tara",
            ],
            "not": ("Çerez içerikleri okunmadı. Dosya zaman damgaları tarayıcı açıkken sürekli değişir; tek başına "
                    "güven kanıtı sayma.")}


# ----------------------------------------------------------------------
# 4) PROJE TARAMASI (açıkta secret / kritik dosya)
# ----------------------------------------------------------------------
_SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Google/Gemini API anahtarı", "KRİTİK"),
    (re.compile(r"gsk_[0-9A-Za-z]{20,}"), "Groq API anahtarı", "KRİTİK"),
    (re.compile(r"sk-[0-9A-Za-z]{20,}"), "OpenAI benzeri API anahtarı", "KRİTİK"),
    (re.compile(r"tvly-[0-9A-Za-z\-]{20,}"), "Tavily API anahtarı", "KRİTİK"),
    (re.compile(r"ghp_[0-9A-Za-z]{30,}"), "GitHub personal token", "KRİTİK"),
    (re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}"), "Slack token", "KRİTİK"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Özel anahtar (private key)", "KRİTİK"),
    (re.compile(r"(?i)(password|passwd|secret|api_key|apikey)\s*[:=]\s*['\"][^'\"]{6,}['\"]"),
     "Gömülü şifre/secret", "YÜKSEK"),
]
_CRITICAL_FILES = {".env", ".env.local", "id_rsa", "id_ed25519", "credentials.json",
                   "service-account.json", "secrets.json", ".npmrc", ".pypirc"}
_IGNORE_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}


def scan_project(path: str):
    """Projeyi tarar: açıkta API anahtarı/şifre/private key, yayınlanmaması gereken dosyalar,
    .git/.env sızıntısı. Kritik olanlar önce sıralanır."""
    path = os.path.abspath(os.path.expanduser(path or ""))
    if not os.path.isdir(path):
        return {"status": "error", "message": "Bu klasör bulunamadı; tam yolunu yaz (örn. Masaüstü\\projem)."}
    findings, seen_files = [], 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        for fn in files:
            seen_files += 1
            if seen_files > 20000:
                break
            fp = os.path.join(root, fn)
            rel = os.path.relpath(fp, path)
            low = fn.lower()
            if low in _CRITICAL_FILES or (low.startswith(".env.") and not low.endswith((".example", ".sample", ".template"))) or low.endswith((".pem", ".p12", ".pfx", ".key")):
                findings.append({"dosya": rel, "tip": "yayınlanmaması gereken dosya",
                                 "onem": "KRİTİK", "satir": 0})
                continue
            if not low.endswith((".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
                                 ".ini", ".cfg", ".md", ".txt", ".html", ".env")):
                continue
            try:
                if os.path.getsize(fp) > 2_000_000:
                    continue
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        for rx, label, sev in _SECRET_PATTERNS:
                            if rx.search(line):
                                findings.append({"dosya": rel, "satir": i,
                                                 "tip": label, "onem": sev})
                                break
            except OSError:
                pass
    order = {"KRİTİK": 0, "YÜKSEK": 1}
    findings.sort(key=lambda f: order.get(f["onem"], 2))
    return {"status": "ok",
            "karar": "ACİL: açıkta secret var" if any(f["onem"] == "KRİTİK" for f in findings)
                     else ("dikkat gerektiren bulgu var" if findings else "temiz görünüyor"),
            "bulgu_sayisi": len(findings), "bulgular": findings[:60],
            "not": "Anahtar/şifre DEĞERLERİ gösterilmez, yalnızca dosya ve satır numarası verilir."}