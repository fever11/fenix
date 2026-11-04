# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""
Web Analiz Motoru (Devil Mod)
-----------------------------
Bir siteyi RAM dostu şekilde çeker (resim/medya indirmez, sadece HTML),
anlamlı metni + yapısal sinyalleri (başlıklar, linkler, formlar, script'ler,
olası sorunlar) çıkarır ve LLM'e özet/denetim için kompakt bir bağlam hazırlar.

Not: Bu modül "güvenlik açığı taraması" yapmaz (bu, hedef sisteme saldırı
anlamına gelebilir ve yetki ister); yalnızca SAYFANIN KENDİ gönderdiği HTML'i
ve herkese açık TLS/DNS/robots bilgisini analiz eder - erişilebilirlik, SEO,
kırık yapı, ağır kaynaklar, eksik meta/güvenlik başlıkları gibi herkese açık,
pasif gözlemler çıkarır. security_inspect() de aynı çizgidedir: sadece GET/TLS
el sıkışması/DNS sorgusu yapar; şifre denemez, exploit çalıştırmaz, hiçbir
sisteme girmez. Amaç site sahibini eksikler konusunda bilgilendirmektir.

check_exposed_files() da aynı disiplinle çalışır: bilinen yollara (`.env`,
`.git/config`, yedek dosyaları...) sade bir GET atar, dönen içeriğin "bu tür
dosyaya benziyor mu" diye imzasına bakar ve SADECE "açıkta mı değil mi"
sonucunu döner - içeriği hiçbir zaman okumaz/saklamaz/göstermez. Aynı şekilde
JS/HTML kaynağında anahtar KALIBI (ör. "AKIA...", "sk_live_...") ararsa da
sadece "böyle bir kalıp var" der, eşleşen değeri asla döndürmez. Amaç: site
sahibine (ya da izinli denetleyen kişiye) "şurayı kapat" diyebilmek; sır
toplamak ya da kullanmak değil.
"""
import re
import json
import hashlib
import socket
import ssl
import datetime as _dt
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0 (FENIX-Analyzer)"}


_SECOND_LEVEL = {"edu.tr", "com.tr", "gov.tr", "org.tr", "net.tr", "k12.tr", "bel.tr", "gen.tr",
                 "co.uk", "ac.uk", "org.uk", "com.au", "co.jp"}


def registered_domain(host):
    """www.bartin.edu.tr -> bartin.edu.tr ; blog.ornek.com -> ornek.com"""
    parts = (host or "").lower().split(":")[0].split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _SECOND_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def fetch_and_parse(url, timeout=20, max_chars=6000):
    if not url.startswith("http"):
        url = "https://" + url

    report = {"url": url}
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout)
    except Exception as e:
        return {"url": url, "error": f"Sayfa çekilemedi: {e}"}

    # Sunucu karakter kodlamasını başlıkta bildirmezse requests ISO-8859-1 varsayar ve Türkçe harfler bozulur
    # ("Gizlilik PolitikasÄ±"). Sayfanın kendi <meta charset> bilgisine, o da yoksa UTF-8'e bakılır.
    if "charset" not in (r.headers.get("content-type") or "").lower():
        mc = re.search(rb"""charset=["']?([A-Za-z0-9_-]+)""", r.content[:4000])
        enc = mc.group(1).decode("ascii", "ignore") if mc else "utf-8"
        try:
            "".encode(enc)
            r.encoding = enc
        except LookupError:
            r.encoding = "utf-8"
    report["status_code"] = r.status_code
    report["final_url"] = r.url
    report["elapsed_ms"] = int(r.elapsed.total_seconds() * 1000)
    report["size_kb"] = round(len(r.content) / 1024, 1)

    # Güvenlik/önemli HTTP başlıkları (pasif gözlem)
    h = {k.lower(): v for k, v in r.headers.items()}
    sec_headers = ["content-security-policy", "strict-transport-security",
                   "x-frame-options", "x-content-type-options", "referrer-policy"]
    report["missing_security_headers"] = [s for s in sec_headers if s not in h]
    report["server"] = h.get("server", "?")

    soup = BeautifulSoup(r.text, "html.parser")

    report["title"] = (soup.title.string.strip() if soup.title and soup.title.string else "(başlık yok)")
    desc = soup.find("meta", attrs={"name": "description"})
    report["meta_description"] = (desc.get("content", "").strip() if desc else "(yok)")
    report["h1_count"] = len(soup.find_all("h1"))
    report["headings"] = [h.get_text(strip=True)[:80] for h in soup.find_all(["h1", "h2"])[:15]]
    report["link_count"] = len(soup.find_all("a"))
    report["image_count"] = len(soup.find_all("img"))
    report["images_without_alt"] = len([i for i in soup.find_all("img") if not i.get("alt")])
    report["form_count"] = len(soup.find_all("form"))
    report["script_count"] = len(soup.find_all("script"))
    report["external_scripts"] = len([s for s in soup.find_all("script") if s.get("src")])
    report["has_viewport"] = bool(soup.find("meta", attrs={"name": "viewport"}))

    # v5.8: raporun UYDURMAMASI için kodda ölçülen ek sinyaller
    html_tag = soup.find("html")
    report["html_lang"] = ((html_tag.get("lang") or "").strip() if html_tag else "")
    can = soup.find("link", rel="canonical")
    report["canonical"] = (can.get("href") or "").strip() if can else ""
    report["has_og"] = bool(soup.find("meta", attrs={"property": re.compile(r"^og:")}))
    rmeta = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    report["noindex"] = bool(rmeta and "noindex" in (rmeta.get("content") or "").lower())
    report["schema_types"] = _schema_types(soup)
    fields = [f for f in soup.find_all(["input", "select", "textarea"])
              if (f.get("type") or "").lower() not in ("hidden", "submit", "button", "image", "reset")]
    label_for = {lb.get("for") for lb in soup.find_all("label") if lb.get("for")}
    report["input_count"] = len(fields)
    report["inputs_without_label"] = sum(
        1 for f in fields if not (f.get("id") in label_for or f.find_parent("label") or f.get("aria-label")
                                  or f.get("aria-labelledby") or f.get("title")))
    report["has_password_field"] = bool(soup.find("input", attrs={"type": re.compile(r"^password$", re.I)}))
    report["lazy_images"] = len([i for i in soup.find_all("img") if (i.get("loading") or "").lower() == "lazy"])
    report["platform"] = _platform(r.text, soup)
    report["x_powered_by"] = h.get("x-powered-by", "")
    all_links = [(a.get("href") or "", a.get_text(" ", strip=True)) for a in soup.find_all("a")]
    report["privacy_links"] = [t[:40] or href[:40] for href, t in all_links
                               if re.search(r"kvkk|gizlilik|privacy|çerez|cerez|cookie|aydınlatma|aydinlatma",
                                            (href + " " + t).lower())][:5]
    report["has_contact"] = any(href.startswith(("tel:", "mailto:")) or re.search(r"iletişim|iletisim|contact",
                                (href + " " + t).lower()) for href, t in all_links)
    report["cart_signals"] = sum(1 for _, t in all_links if re.search(
        r"sepete ekle|sepet|add to cart|buy now|satın al|satin al|checkout|ödeme", t.lower()))
    report["cart_signals"] += len(soup.find_all(["button", "input"], string=re.compile(
        r"sepete ekle|add to cart|satın al|buy now", re.I)))

    # Aynı siteye (alt alan adları dahil: bolum.universite.edu.tr) giden linkler + bağlantı metinleri
    base_dom = registered_domain(urlparse(r.url).netloc)
    links, labels, seen = [], [], set()
    for a in soup.find_all("a", href=True):
        full = urljoin(r.url, a["href"]).split("#")[0]
        host = urlparse(full).netloc.lower()
        if (full.startswith("http") and (host == base_dom or host.endswith("." + base_dom))
                and full not in seen and not re.search(r"\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?)$", full, re.I)):
            seen.add(full)
            links.append(full)
            labels.append(a.get_text(" ", strip=True)[:80])
        if len(links) >= 80:
            break
    report["link_labels"] = labels
    report["links"] = links

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    report["text_excerpt"] = text[:max_chars]
    report["text_length"] = len(text)
    report["word_count"] = len(text.split())
    report["price_mentions"] = len(re.findall(r"(?:₺|\$|€|£)\s?\d|\d[\d.,]*\s?(?:₺|TL\b|USD\b|EUR\b)", text))
    report["text_hash"] = hashlib.md5(text[:20000].lower().encode("utf-8", "ignore")).hexdigest()
    return report


def _schema_types(soup):
    """Sayfadaki schema.org (JSON-LD) türleri: Product, Organization, Course..."""
    types = []
    for sc in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(sc.string or sc.get_text() or "")
        except Exception:
            continue
        stack = [data]
        while stack and len(types) < 40:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                t = d.get("@type")
                if isinstance(t, str):
                    types.append(t)
                elif isinstance(t, list):
                    types.extend(x for x in t if isinstance(x, str))
                for k in ("@graph", "itemListElement", "offers", "mainEntity", "item"):
                    if k in d:
                        stack.append(d[k])
    return sorted(set(types))[:15]


def _platform(raw, soup):
    """Sitenin kurulu olduğu altyapı (herkese açık izlerden)."""
    low = raw.lower()
    out = []
    for name, marks in (("Shopify", ("cdn.shopify.com", "shopify.theme")), ("WordPress", ("/wp-content/",)),
                        ("WooCommerce", ("woocommerce",)), ("Wix", ("static.wixstatic.com",)),
                        ("Ticimax", ("ticimax",)), ("IdeaSoft", ("ideasoft",)), ("Next.js", ("/_next/static",)),
                        ("Squarespace", ("squarespace.com",))):
        if any(m in low for m in marks):
            out.append(name)
    gen = soup.find("meta", attrs={"name": "generator"})
    if gen and gen.get("content") and not any(o.lower() in gen["content"].lower() for o in out):
        out.append(gen["content"][:40])
    return out


# ---------------- Pasif güvenlik/durum gözlemleri (herkese açık bilgi) ----------------
def _tls_info(host, port=443, timeout=10):
    """TLS/sertifika durumu: süresi dolmuş mu, hangi protokol, kim imzalamış. Sadece el sıkışıp
    sertifikayı okur; parola/anahtar denemez."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                proto = ssock.version()
        not_after = _dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days_left = (not_after - _dt.datetime.utcnow()).days
        issuer = dict(x[0] for x in cert.get("issuer", []))
        return {
            "tls_protokol": proto,
            "tls_veren": issuer.get("organizationName") or issuer.get("commonName", "?"),
            "tls_bitis": not_after.strftime("%Y-%m-%d"),
            "tls_kalan_gun": days_left,
            "tls_suresi_dolmus": days_left < 0,
            "tls_zayif_protokol": proto in ("TLSv1", "TLSv1.1", "SSLv3", "SSLv2"),
        }
    except Exception as e:
        return {"tls_hata": str(e)[:160]}


def _dns_info(host, timeout=6):
    """DNS çözümlemesi + (varsa) WHOIS kayıt yaşı. Herkese açık alan adı kayıt bilgisidir."""
    info = {}
    try:
        info["ip"] = socket.gethostbyname(host)
    except Exception as e:
        info["dns_hata"] = str(e)[:120]
        return info
    try:
        import whois as _whois
        socket.setdefaulttimeout(timeout)
        w = _whois.whois(host)
        created = w.creation_date
        if isinstance(created, list):
            created = created[0]
        if created and hasattr(created, "year"):
            info["alan_adi_olusturma"] = str(created)[:10]
            try:
                info["alan_adi_yas_gun"] = (_dt.datetime.now() - created.replace(tzinfo=None)).days
            except Exception:
                pass
        if w.registrar:
            info["kayit_firmasi"] = str(w.registrar)[:120]
    except Exception:
        pass        # whois paketi kurulu değil ya da sorgu engellendi: sessizce geç
    finally:
        socket.setdefaulttimeout(None)
    return info


def _robots_info(base_url, timeout=10):
    """robots.txt / sitemap.xml var mı, hangi yolları (sahibi kendisi) işaretli. Herkese açık dosya okunur."""
    out = {}
    try:
        r = requests.get(urljoin(base_url, "/robots.txt"), headers=_HEADERS, timeout=timeout)
        if r.status_code == 200 and r.text.strip():
            out["robots_txt"] = True
            out["robots_disallow"] = re.findall(r"(?im)^disallow:\s*(\S+)", r.text)[:20]
        else:
            out["robots_txt"] = False
    except Exception:
        out["robots_txt"] = None
    try:
        r = requests.get(urljoin(base_url, "/sitemap.xml"), headers=_HEADERS, timeout=timeout)
        out["sitemap_xml"] = (r.status_code == 200)
    except Exception:
        out["sitemap_xml"] = None
    return out


def _tech_fingerprint(headers, soup):
    """Sunucu/CMS parmak izi: HTTP başlıkları + meta generator etiketi (hepsi herkese açık)."""
    out = {}
    h = {k.lower(): v for k, v in headers.items()}
    if "x-powered-by" in h:
        out["x_powered_by"] = h["x-powered-by"]
    gen = soup.find("meta", attrs={"name": "generator"})
    if gen and gen.get("content"):
        out["generator"] = gen["content"][:120]
    return out


def security_inspect(url, timeout=15, check_exposure=True):
    """Bir site için pasif güvenlik/durum gözlemleri: TLS/sertifika, DNS/WHOIS, robots/sitemap,
    teknoloji parmak izi, (check_exposure=True ise) bilinen açık dosya yolları ve JS'te anahtar kalıbı.
    SADECE herkese açık, GET/TLS-el-sıkışma ile okunabilen bilgidir; içerik/değer asla saklanmaz.
    Zafiyet taraması, şifre denemesi ya da sisteme giriş YAPMAZ; amaç bilgilendirmedir."""
    if not url.startswith("http"):
        url = "https://" + url
    host = urlparse(url).netloc.split(":")[0]
    out = {"url": url, "host": host}
    out.update(_tls_info(host))
    out.update(_dns_info(host))
    out.update(_robots_info(url, timeout=timeout))
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout)
        soup = BeautifulSoup(r.text, "html.parser")
        out.update(_tech_fingerprint(r.headers, soup))
        if check_exposure:
            out["acik_dosyalar"] = check_exposed_files(url, timeout=timeout)
            out["anahtar_kalibi_bulunan"] = scan_js_for_key_patterns(url, soup, timeout=timeout)
    except Exception as e:
        out["sayfa_hata"] = str(e)[:160]
    return out


def security_summary_md(sec):
    """security_inspect() çıktısını kısa, okunur Markdown maddelerine çevirir (rapora gömülür)."""
    lines = []
    if "tls_hata" not in sec:
        flags = []
        if sec.get("tls_suresi_dolmus"):
            flags.append("⚠️ SÜRESİ DOLMUŞ")
        if sec.get("tls_zayif_protokol"):
            flags.append(f"⚠️ zayıf protokol ({sec.get('tls_protokol')})")
        lines.append(f"- **TLS/Sertifika:** {sec.get('tls_protokol', '?')} • veren: {sec.get('tls_veren', '?')} • "
                     f"bitiş: {sec.get('tls_bitis', '?')} ({sec.get('tls_kalan_gun', '?')} gün kaldı)"
                     + (" — " + ", ".join(flags) if flags else ""))
    else:
        lines.append(f"- **TLS/Sertifika:** okunamadı ({sec['tls_hata']})")

    if sec.get("ip"):
        bits = [f"IP: {sec['ip']}"]
        if sec.get("alan_adi_olusturma"):
            yas = f" (~{sec['alan_adi_yas_gun'] // 365} yıl önce)" if sec.get("alan_adi_yas_gun") else ""
            bits.append(f"alan adı kaydı: {sec['alan_adi_olusturma']}{yas}")
        if sec.get("kayit_firmasi"):
            bits.append(f"kayıt firması: {sec['kayit_firmasi']}")
        lines.append(f"- **DNS/Kayıt:** {' • '.join(bits)}")
    elif sec.get("dns_hata"):
        lines.append(f"- **DNS:** çözümlenemedi ({sec['dns_hata']})")

    robots_bits = []
    if sec.get("robots_txt") is True:
        robots_bits.append(f"robots.txt var ({len(sec.get('robots_disallow', []))} gizli yol işaretli)")
    elif sec.get("robots_txt") is False:
        robots_bits.append("robots.txt yok")
    robots_bits.append("sitemap.xml var" if sec.get("sitemap_xml") else "sitemap.xml yok")
    lines.append(f"- **robots/sitemap:** {', '.join(robots_bits)}")

    tech_bits = []
    if sec.get("generator"):
        tech_bits.append(f"üretici: {sec['generator']}")
    if sec.get("x_powered_by"):
        tech_bits.append(f"X-Powered-By: {sec['x_powered_by']}")
    if tech_bits:
        lines.append(f"- **Teknoloji izi:** {', '.join(tech_bits)}")

    exposed = sec.get("acik_dosyalar") or []
    if exposed:
        lines.append(f"- **⚠️ Açıkta kalmış dosya(lar) bulundu ({len(exposed)}):**")
        for e in exposed:
            lines.append(f"  - `{e['yol']}` ({e['ad']}, ~{e['boyut_kb']} KB) — {e['neden_onemli']}. "
                         f"**İçeriği okunmadı/kaydedilmedi**; acilen erişime kapatılmalı ve içindeki "
                         f"bilgiler (şifre/anahtar) hemen yenilenmeli.")
    elif "acik_dosyalar" in sec:
        lines.append("- **Açık dosya taraması:** bilinen hassas dosya yollarında (.env, .git, yedekler) "
                     "açık bir şey bulunamadı.")

    key_hits = sec.get("anahtar_kalibi_bulunan") or []
    if key_hits:
        lines.append(f"- **⚠️ Script dosyalarında olası anahtar kalıbı ({len(key_hits)} dosya):**")
        for h in key_hits:
            kinds = ", ".join(f"{k} ×{n}" for k, n in h["bulunan_kaliplar"].items())
            lines.append(f"  - `{h['dosya']}`: {kinds} — **değerler okunmadı/kaydedilmedi**; ön yüz "
                         f"kodunda anahtar varsa herkes tarayıcı konsolundan görebilir, taşınmalı/iptal edilmeli.")
    return "\n".join(lines)


# ---------------- Açık dosya kontrolü (var/yok - İÇERİK ASLA OKUNMAZ) ----------------
# path -> (açıklama, "neden önemli" notu, imza deseni: içerik bu deseni içermiyorsa custom-404 sayılır)
_SENSITIVE_PATHS = {
    "/.env": ("Ortam değişkenleri dosyası",
             "genelde veritabanı şifresi, API anahtarları ve gizli anahtarlar içerir",
             re.compile(r"^\s*[A-Z_][A-Z0-9_]*\s*=", re.M)),
    "/.env.local": ("Ortam değişkenleri dosyası (local)",
                    "genelde veritabanı şifresi, API anahtarları ve gizli anahtarlar içerir",
                    re.compile(r"^\s*[A-Z_][A-Z0-9_]*\s*=", re.M)),
    "/.env.production": ("Ortam değişkenleri dosyası (production)",
                         "canlı ortamın şifrelerini/anahtarlarını içerir - en kritik olanı",
                         re.compile(r"^\s*[A-Z_][A-Z0-9_]*\s*=", re.M)),
    "/.git/config": ("Git deposu yapılandırması",
                     "açık kalırsa .git/ üzerinden sitenin TÜM KAYNAK KODU indirilebilir",
                     re.compile(r"\[core\]")),
    "/.git/HEAD": ("Git deposu",
                  "açık kalırsa .git/ üzerinden sitenin TÜM KAYNAK KODU indirilebilir",
                  re.compile(r"^ref:\s*refs/")),
    "/backup.sql": ("Veritabanı yedeği", "kullanıcı tablosu, şifre özetleri, kişisel veri içerebilir",
                    re.compile(r"(?i)insert into|create table")),
    "/database.sql": ("Veritabanı yedeği", "kullanıcı tablosu, şifre özetleri, kişisel veri içerebilir",
                      re.compile(r"(?i)insert into|create table")),
    "/dump.sql": ("Veritabanı yedeği", "kullanıcı tablosu, şifre özetleri, kişisel veri içerebilir",
                 re.compile(r"(?i)insert into|create table")),
    "/wp-config.php.bak": ("WordPress yapılandırma yedeği", "veritabanı şifresini ve gizli anahtarları içerir",
                          re.compile(r"(?i)DB_PASSWORD|define\(")),
    "/.htpasswd": ("Eski tip erişim şifre dosyası", "kullanıcı adı ve şifre özetlerini içerir",
                  re.compile(r"^[^:\s]+:\$")),
}


def check_exposed_files(base_url, timeout=8):
    """Bilinen yollara (`.env`, `.git/config`, yedek dosyaları...) sade bir GET atar; dönen içeriği
    İMZASINA bakıp "bu dosyaya benziyor mu" diye kontrol eder (çoğu site olmayan yol için 200 + özel
    404 sayfası döner, bunu ayıklamak için). İçerik HİÇBİR ZAMAN okunup saklanmaz/gösterilmez - sadece
    bulundu/bulunamadı + ne tür risk taşıdığına dair sabit bir açıklama döner."""
    out = []
    for path, (ad, neden, sig) in _SENSITIVE_PATHS.items():
        try:
            r = requests.get(urljoin(base_url, path), headers=_HEADERS, timeout=timeout)
            if r.status_code == 200 and sig.search(r.text[:4000]):
                out.append({"yol": path, "ad": ad, "neden_onemli": neden, "boyut_kb": round(len(r.content) / 1024, 1)})
        except Exception:
            continue
    return out


# ---------------- Kod/JS içinde unutulmuş anahtar KALIBI (değer asla döndürülmez) ----------------
_KEY_PATTERNS = [
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Google API Key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("Stripe Live Key", re.compile(r"\bsk_live_[0-9A-Za-z]{20,}\b")),
    ("Genel Bearer/Secret Token", re.compile(r"(?i)(?:secret|api[_-]?key|token|password)\s*[:=]\s*['\"][A-Za-z0-9+/_\-]{16,}['\"]")),
    ("Özel Anahtar (PEM)", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
]


def scan_js_for_key_patterns(page_url, soup, timeout=8, max_files=6, max_bytes=300_000):
    """Ana sayfadaki script dosyalarının İLK max_bytes'ını indirip bilinen anahtar KALIPLARINI arar.
    Eşleşen DEĞERİ asla döndürmez; sadece "bu dosyada bu türden N kalıp bulundu" der."""
    out = []
    srcs = [urljoin(page_url, s.get("src")) for s in soup.find_all("script", src=True)][:max_files]
    for src in srcs:
        try:
            r = requests.get(src, headers=_HEADERS, timeout=timeout, stream=True)
            content = r.raw.read(max_bytes, decode_content=True).decode("utf-8", "ignore")
        except Exception:
            continue
        hits = {ad: len(pat.findall(content)) for ad, pat in _KEY_PATTERNS if pat.search(content)}
        if hits:
            out.append({"dosya": src, "bulunan_kaliplar": hits})
    return out


def build_analysis_prompt(report, user_goal=""):
    if "error" in report:
        return f"Siteyi analiz edemedim: {report['error']}"
    lines = [
        "Aşağıda bir web sayfasının pasif analizinden çıkan teknik veriler var. "
        "Bunları kullanarak Türkçe, net ve teknik bir DURUM RAPORU çıkar: "
        "genel değerlendirme, tespit edilen sorunlar/riskler (SEO, erişilebilirlik, "
        "performans, eksik güvenlik başlıkları, yapısal hatalar) ve somut öneriler. "
        "Maddelerle değil akıcı paragraflarla yaz, sonunda kısa bir 'öncelikli "
        "aksiyonlar' bölümü olsun.",
    ]
    if user_goal:
        lines.append(f"\nKullanıcının özel isteği: {user_goal}")
    lines.append("\n--- TEKNİK VERİLER ---")
    for k, v in report.items():
        if k in ("text_excerpt", "links", "link_labels"):
            continue
        lines.append(f"{k}: {v}")
    lines.append(f"\n--- SAYFA METNİ (kısaltılmış) ---\n{report.get('text_excerpt','')}")
    return "\n".join(lines)
