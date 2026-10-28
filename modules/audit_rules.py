# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · All rights reserved
"""
Rapor kuralları (v5.8)
---------------------
Önceki sürümlerde site denetimi ve araştırma raporlarını model tek başına yazıyordu: her siteye aynı
şablon, ölçülmemiş şeyler ("canonical yok", "schema yok"), tutarsız sayılar ("8-5-5 görselden 3-3-3"),
uydurma imzalar. Artık:

  * Ölçümler ve bulgular KODDA çıkarılır (kanıtıyla, hangi sayfada olduğuyla, önem derecesiyle).
  * Site türü (e-ticaret, eğitim, giriş ekranlı uygulama, kurumsal, kişisel) kodda belirlenir ve
    bulgular / kontrol listesi türe göre değişir.
  * Model sadece yorumlar: özet, türe özel değerlendirme, öncelik sırası. Yeni sayı ya da ölçülmemiş
    bir şey yazamaz; çıktısı temizlenir (emoji, imza, kendi kaynak listesi).
  * Araştırmada konu türüne göre başlıklar seçilir; ilgisiz kaynaklar elenir, kaynak numaraları
    yeniden sıralanır; bilgi yetersizse rapor yerine net bir açıklama verilir.
"""
import re
from urllib.parse import urlparse, urlunparse

# ======================================================================
# Ortak
# ======================================================================
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF️‍]")
_SIGNATURE_RE = re.compile(r"^\s*[*_]*\s*(hazırlayan|hazirlayan|prepared by|rapor(u)? hazırlayan)\b.*$",
                           re.IGNORECASE | re.MULTILINE)


def sanitize_report(text):
    """Model çıktısını temizler: emoji, uydurma imza satırları, modelin kendi yazdığı kaynak listesi."""
    t = text or ""
    t = _SIGNATURE_RE.sub("", t)
    t = _EMOJI_RE.sub("", t)
    t = re.split(r"\n#{1,3}\s*(?:Kaynaklar|Kaynakça|Taranan Sayfalar)\s*\n", t)[0]
    t = re.sub(r"(?m)^(#{1,6})\s+", r"\1 ", t)           # '##  Özet' -> '## Özet'
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


# ======================================================================
# SİTE DENETİMİ
# ======================================================================
def normalize_url(u):
    """Aynı sayfanın farklı yazımlarını birleştirir: sondaki '/', index.html, #parça, utm parametreleri."""
    p = urlparse(u)
    path = re.sub(r"/(index|default)\.(html?|php|aspx?)$", "/", p.path, flags=re.I) or "/"
    if path != "/":
        path = path.rstrip("/")
    q = "&".join(x for x in p.query.split("&") if x and not x.lower().startswith(("utm_", "fbclid", "gclid")))
    return urlunparse((p.scheme.lower(), p.netloc.lower().removeprefix("www."), path, "", q, ""))


def pick_links(root_url, links, limit):
    """Taranacak alt sayfaları seçer: aynı sayfanın tekrarlarını atar, farklı bölümlerden (yol başı)
    sayfa almaya öncelik verir (hep /urun/1, /urun/2 gibi aynı türden sayfa seçilmesin)."""
    seen = {normalize_url(root_url)}
    uniq = []
    for l in links:
        n = normalize_url(l)
        if n not in seen and not re.search(r"(logout|cikis|çıkış|signout|/cart/add|/wp-admin)", l, re.I):
            seen.add(n)
            uniq.append(l)
    first, rest, heads = [], [], set()
    for l in uniq:
        head = (urlparse(l).path.strip("/").split("/") or [""])[0].lower()
        (rest if head in heads else first).append(l)
        heads.add(head)
    return (first + rest)[:limit]


def dedupe_pages(pages):
    """Aynı içeriği veren adresleri tek sayfa sayar. Döner: (benzersiz_sayfalar, [(asil_url, tekrar_url), ...])."""
    out, dups, by_hash = [], [], {}
    for p in pages:
        h = p.get("text_hash")
        if h and h in by_hash and p.get("text_length", 0) > 200:
            dups.append((by_hash[h]["final_url"], p["final_url"]))
            continue
        if h:
            by_hash[h] = p
        out.append(p)
    return out, dups


# Sıra önemli: puan eşitse içerik türü (e-ticaret, eğitim) giriş ekranından önce gelir
SITE_TYPES = {
    "eticaret": "e-ticaret / online mağaza",
    "egitim": "eğitim kurumu / kurs sitesi",
    "uygulama": "giriş ekranlı web uygulaması",
    "kurumsal": "kurumsal / tanıtım sitesi",
    "kisisel": "kişisel / tek sayfalık site",
}


def classify_site(pages, sec=None):
    """Site türünü ölçülen izlerden belirler. Döner: {'tur', 'etiket', 'ikincil': [...], 'kanit': [...]}"""
    host = urlparse(pages[0]["final_url"]).netloc.lower() if pages else ""
    score = {k: 0 for k in SITE_TYPES}
    why = {k: [] for k in SITE_TYPES}

    def add(kind, pts, reason):
        score[kind] += pts
        if reason not in why[kind]:
            why[kind].append(reason)

    schema = {t for p in pages for t in p.get("schema_types", [])}
    plats = {x for p in pages for x in p.get("platform", [])}
    paths = " ".join(urlparse(p["final_url"]).path.lower() for p in pages)
    alltext = " ".join((p.get("title", "") + " " + " ".join(p.get("headings", []))) for p in pages).lower()

    if schema & {"Product", "Offer", "AggregateOffer", "ItemList"} and "Product" in schema:
        add("eticaret", 4, "schema.org Product işaretlemesi var")
    if plats & {"Shopify", "WooCommerce", "Ticimax", "IdeaSoft"}:
        add("eticaret", 4, f"e-ticaret altyapısı: {', '.join(sorted(plats & {'Shopify', 'WooCommerce', 'Ticimax', 'IdeaSoft'}))}")
    if sum(p.get("cart_signals", 0) for p in pages) >= 2:
        add("eticaret", 2, "sepet / satın al bağlantıları var")
    if re.search(r"/(products?|urun|urunler|collections?|kategori|shop|magaza|sepet|cart)\b", paths):
        add("eticaret", 2, "ürün/koleksiyon/sepet sayfaları var")
    if sum(1 for p in pages if p.get("price_mentions", 0) >= 3) >= 2:
        add("eticaret", 1, "birden çok sayfada fiyat geçiyor")

    if any(p.get("has_password_field") for p in pages):
        add("uygulama", 3, "şifre alanı olan giriş formu var")
    if re.search(r"/(auth|login|giris|signin|uye-ol|register|kayit|dashboard|panel)\b", paths):
        add("uygulama", 1, "giriş/kayıt sayfaları var")

    if host.endswith((".edu.tr", ".edu", ".k12.tr", ".ac.uk")):
        add("egitim", 4, "eğitim kurumu alan adı (.edu)")
    if schema & {"Course", "EducationalOrganization", "CollegeOrUniversity", "School"}:
        add("egitim", 3, "schema.org eğitim işaretlemesi var")
    if re.search(r"\b(eğitim|egitim|kurs|ders|öğrenci|ogrenci|akademi|okul|üniversite|universite|course|academy)", alltext):
        add("egitim", 2, "başlıklarda eğitim/kurs/ders geçiyor")
    if re.search(r"/(egitim\w*|kurs\w*|courses?|ders\w*|akademi\w*|ogrenci\w*|mufredat|bolum\w*)", paths):
        add("egitim", 2, "eğitim/kurs sayfaları var")

    if any(p.get("has_contact") for p in pages):
        add("kurumsal", 1, "iletişim bilgisi var")
    if re.search(r"/(hakkimizda|about|kurumsal|company|iletisim|contact)\b", paths):
        add("kurumsal", 1, "hakkımızda/iletişim sayfaları var")
    if schema & {"Organization", "Corporation", "LocalBusiness"}:
        add("kurumsal", 1, "schema.org Organization işaretlemesi var")

    if len(pages) <= 2 and sum(p.get("link_count", 0) for p in pages) < 15:
        add("kisisel", 3, "çok az sayfa ve bağlantı")

    ranked = sorted(score, key=lambda k: -score[k])
    best = ranked[0] if score[ranked[0]] >= 2 else "kurumsal"
    secondary = [k for k in ranked[1:] if score[k] >= 3]
    # Kurslarını online satan ve üye girişi olan bir dil okulu: eğitim + e-ticaret + uygulama olabilir
    return {"tur": best, "etiket": SITE_TYPES[best], "ikincil": secondary,
            "ikincil_etiket": [SITE_TYPES[k] for k in secondary],
            "kanit": why[best] or ["belirgin bir tür izi yok, genel kurumsal site kabul edildi"]}


TYPE_FOCUS = {
    "eticaret": ("Ürün sayfaları ve satın alma yolu: ürün işaretlemesi (fiyat/stok arama sonuçlarında görünsün), ürün "
                 "görsellerinin alt metni, kategori sayfalarının benzersiz başlıkları, sepet/ödeme güveni, mesafeli satış "
                 "ve KVKK bağlantıları, çok sayıda script'in satın almayı yavaşlatması."),
    "uygulama": ("Giriş ekranı ve kullanıcı güveni: giriş sayfasının başka sitede gizlice gösterilmesine karşı koruma "
                 "(X-Frame-Options / CSP frame-ancestors), HSTS, aynı giriş sayfasının birden çok adreste olması, "
                 "gizlilik/KVKK/çerez metinlerine erişim, form alanlarının erişilebilirliği, giriş sayfalarının "
                 "arama sonuçlarında gereksiz görünmesi."),
    "egitim": ("Öğrenci/aday gözüyle bilgiye ulaşma: program/kurs bilgisinin bulunabilirliği, iletişim, kamu ve eğitim "
               "sitelerinde erişilebilirliğin (alt metin, dil etiketi, form etiketleri) daha da önemli olması, "
               "kurs/kurum işaretlemesi, sayfa başlıklarının benzersizliği."),
    "kurumsal": ("Tanıtım ve güven: şirketi doğru anlatan başlık/açıklamalar, iletişim bilgisinin bulunabilirliği, "
                 "kurum işaretlemesi, güvenlik başlıkları ve sertifika."),
    "kisisel": ("Az sayfalı site: temel SEO etiketleri, paylaşım önizlemesi (Open Graph), arama motorlarının siteyi "
                "bulabilmesi (robots/sitemap), güvenlik başlıkları."),
}

_SEV_ORDER = {"kritik": 0, "önemli": 1, "iyileştirme": 2}


def _pages_str(nums, total):
    if len(nums) == total and total > 1:
        return "tüm sayfalarda"
    return "sayfa " + ", ".join(str(n) for n in nums)


def build_findings(pages, sec, site, dups=()):
    """Ölçülen veriden bulguları çıkarır. Döner: (bulgular, olumlular, olculmeyenler).
    Her bulgu: {'id','seviye','alan','baslik','kanit'}; numaralar sayfa listesindeki sırayla aynıdır."""
    sec = sec or {}
    n = len(pages)
    kind = site.get("tur")
    kinds = {kind, *site.get("ikincil", [])}
    F, OK = [], []

    def f(seviye, alan, baslik, kanit):
        F.append({"seviye": seviye, "alan": alan, "baslik": baslik, "kanit": kanit})

    idx = list(range(1, n + 1))
    has_login = [i for i, p in zip(idx, pages) if p.get("has_password_field")]

    # ---- Güvenlik: TLS, açık dosya, anahtar kalıbı ----
    if "tls_hata" in sec:
        f("önemli", "Güvenlik", "TLS sertifikası okunamadı", sec["tls_hata"])
    else:
        days = sec.get("tls_kalan_gun")
        if sec.get("tls_suresi_dolmus"):
            f("kritik", "Güvenlik", "TLS sertifikasının süresi dolmuş", f"bitiş {sec.get('tls_bitis')}")
        elif isinstance(days, int) and days < 15:
            f("kritik", "Güvenlik", "TLS sertifikası çok yakında bitiyor",
              f"{sec.get('tls_bitis')} ({days} gün kaldı); otomatik yenileme çalışıyor mu kontrol edilmeli")
        elif isinstance(days, int) and days < 30:
            f("önemli", "Güvenlik", "TLS sertifikası yakında bitiyor", f"{sec.get('tls_bitis')} ({days} gün kaldı)")
        elif isinstance(days, int) and days < 45:
            f("iyileştirme", "Güvenlik", "TLS sertifikasının bitişi yaklaşıyor",
              f"{sec.get('tls_bitis')} ({days} gün kaldı); otomatik yenilemenin açık olduğundan emin olunmalı")
        if sec.get("tls_zayif_protokol"):
            f("kritik", "Güvenlik", "Eski ve zayıf TLS protokolü", sec.get("tls_protokol", "?"))
        elif sec.get("tls_protokol") == "TLSv1.2":
            f("iyileştirme", "Güvenlik", "TLS 1.3 desteklenmiyor (1.2 kullanılıyor)",
              "TLS 1.2 hâlâ güvenli kabul edilir; 1.3 biraz daha hızlı ve modern")
        elif sec.get("tls_protokol") and isinstance(days, int) and days >= 45:
            OK.append(f"TLS sertifikası geçerli ({sec.get('tls_protokol')}, {sec.get('tls_veren', '?')}, {days} gün var)")
    exposed = sec.get("acik_dosyalar") or []
    if exposed:
        f("kritik", "Güvenlik", "Hassas dosya(lar) herkese açık",
          "; ".join(f"{e['yol']} ({e['ad']})" for e in exposed) + " — içerik okunmadı; hemen kapatılmalı, içindeki "
          "şifre/anahtarlar yenilenmeli")
    elif "acik_dosyalar" in sec:
        OK.append("Bilinen hassas dosya yollarında (.env, .git, yedekler) açık dosya yok")
    keys = sec.get("anahtar_kalibi_bulunan") or []
    if keys:
        f("kritik", "Güvenlik", "Script dosyalarında olası API anahtarı kalıbı",
          "; ".join(k["dosya"] for k in keys) + " — değerler okunmadı; ön yüz kodundaki anahtarlar herkes tarafından görülebilir")

    # ---- Güvenlik başlıkları (her sayfa için ölçüldü) ----
    names = {"content-security-policy": "Content-Security-Policy (CSP)",
             "strict-transport-security": "Strict-Transport-Security (HSTS)",
             "x-frame-options": "X-Frame-Options", "x-content-type-options": "X-Content-Type-Options",
             "referrer-policy": "Referrer-Policy"}
    missing_any = False
    for hdr, label in names.items():
        miss = [i for i, p in zip(idx, pages) if hdr in p.get("missing_security_headers", [])]
        if not miss:
            continue
        missing_any = True
        sev = "önemli" if hdr in ("content-security-policy", "strict-transport-security") else "iyileştirme"
        why = ""
        if hdr == "x-frame-options" and has_login and set(has_login) & set(miss):
            sev = "kritik" if "content-security-policy" in pages[has_login[0] - 1].get("missing_security_headers", []) else "önemli"
            why = " — giriş sayfası başka bir sitenin içinde gizlice gösterilebilir (clickjacking)"
        f(sev, "Güvenlik", f"{label} başlığı yok", _pages_str(miss, n) + why)
    if not missing_any and pages:
        OK.append("Beş temel güvenlik başlığının hepsi var (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)")
    xpb = sec.get("x_powered_by") or next((p.get("x_powered_by") for p in pages if p.get("x_powered_by")), "")
    if xpb:
        f("iyileştirme", "Güvenlik", "Sunucu altyapısı başlıkta ilan ediliyor", f"X-Powered-By: {xpb}")

    # ---- robots / sitemap ----
    if sec.get("robots_txt") is False:
        f("iyileştirme", "SEO", "robots.txt yok", "arama motorlarına tarama kuralı verilmiyor")
    if sec.get("sitemap_xml") is False:
        f("önemli" if kind in ("eticaret", "egitim", "kurumsal") and n > 2 else "iyileştirme", "SEO",
          "sitemap.xml yok", "arama motorları sayfaları keşfetmekte zorlanabilir")
    if sec.get("robots_txt") and sec.get("sitemap_xml"):
        OK.append("robots.txt ve sitemap.xml mevcut")

    # ---- SEO ----
    no_desc = [i for i, p in zip(idx, pages) if p.get("meta_description", "(yok)") in ("(yok)", "")]
    if no_desc:
        f("önemli" if len(no_desc) > n / 2 else "iyileştirme", "SEO", "Meta açıklaması eksik", _pages_str(no_desc, n))
    elif pages:
        OK.append("Tüm sayfalarda meta açıklaması var")
    descs = {}
    for i, p in zip(idx, pages):
        d = p.get("meta_description", "(yok)")
        if d not in ("(yok)", ""):
            descs.setdefault(d, []).append(i)
    rep_desc = [v for v in descs.values() if len(v) > 1]
    if rep_desc:
        f("iyileştirme", "SEO", "Aynı meta açıklaması birden çok sayfada",
          "; ".join(_pages_str(v, n) for v in rep_desc))
    titles = {}
    for i, p in zip(idx, pages):
        titles.setdefault(p.get("title", ""), []).append(i)
    rep_title = {t: v for t, v in titles.items() if len(v) > 1}
    if rep_title:
        f("önemli", "SEO", "Aynı sayfa başlığı birden çok sayfada",
          "; ".join(f"\"{t[:60]}\" ({_pages_str(v, n)})" for t, v in rep_title.items()))
    elif n > 1:
        OK.append("Sayfa başlıkları birbirinden farklı")
    no_h1 = [i for i, p in zip(idx, pages) if p.get("h1_count", 0) == 0]
    multi_h1 = [i for i, p in zip(idx, pages) if p.get("h1_count", 0) > 1]
    if no_h1:
        f("önemli" if len(no_h1) > n / 2 else "iyileştirme", "SEO", "H1 ana başlığı yok", _pages_str(no_h1, n))
    if multi_h1:
        f("iyileştirme", "SEO", "Birden fazla H1 başlığı",
          ", ".join(f"sayfa {i} ({pages[i - 1]['h1_count']} adet)" for i in multi_h1))
    if not no_h1 and not multi_h1 and pages:
        OK.append("Her sayfada tek bir H1 başlığı var")
    if pages and all(not p.get("canonical") for p in pages):
        f("önemli" if dups else "iyileştirme", "SEO", "Canonical etiketi hiçbir sayfada yok",
          "aynı içeriğin farklı adresleri arama motorunda ayrı sayfa sayılabilir")
    schema = sorted({t for p in pages for t in p.get("schema_types", [])})
    if schema:
        OK.append("schema.org işaretlemesi var: " + ", ".join(schema[:8]))
    elif "eticaret" not in kinds:        # e-ticarette aşağıdaki 'ürün işaretlemesi' bulgusu bunu kapsar
        f("iyileştirme", "SEO", "schema.org (JSON-LD) işaretlemesi yok",
          "arama sonuçlarında zengin görünüm (kurs, kurum, iletişim bilgisi) çıkmaz")
    noidx = [i for i, p in zip(idx, pages) if p.get("noindex")]
    if 1 in noidx:
        f("kritik", "SEO", "Ana sayfa arama motorlarına kapalı (noindex)", "sayfa 1")
    if pages and not any(p.get("has_og") for p in pages):
        f("iyileştirme", "SEO", "Paylaşım önizlemesi (Open Graph) yok",
          "WhatsApp/sosyal medyada paylaşılınca başlık ve görsel düzgün görünmez")
    for orig, dup in dups:
        f("önemli", "İçerik", "Aynı içerik iki farklı adreste", f"{dup} ile {orig} aynı içeriği veriyor")

    # ---- Erişilebilirlik ----
    if pages and all(not p.get("html_lang") for p in pages):
        f("önemli", "Erişilebilirlik", "Sayfa dili belirtilmemiş (<html lang>)",
          "ekran okuyucular Türkçe metni yanlış telaffuz eder")
    elif pages:
        OK.append(f"Sayfa dili belirtilmiş (lang=\"{next(p['html_lang'] for p in pages if p.get('html_lang'))}\")")
    img_total = sum(p.get("image_count", 0) for p in pages)
    img_noalt = sum(p.get("images_without_alt", 0) for p in pages)
    if img_noalt:
        per = ", ".join(f"s{i}: {p['images_without_alt']}/{p['image_count']}" for i, p in zip(idx, pages)
                        if p.get("images_without_alt"))
        f("önemli" if img_noalt * 2 > img_total else "iyileştirme", "Erişilebilirlik",
          "Görsellerde alt metni eksik",
          f"sayfalardaki {img_total} görselin {img_noalt} tanesinde (sayfa başına alt'sız/toplam: {per}); "
          "logo gibi her sayfada tekrar eden görseller birden çok sayılır")
    elif img_total:
        OK.append(f"Sayfalardaki {img_total} görselin hepsinde alt metni var")
    inp_total = sum(p.get("input_count", 0) for p in pages)
    inp_bad = sum(p.get("inputs_without_label", 0) for p in pages)
    if inp_bad:
        f("önemli", "Erişilebilirlik", "Form alanlarında etiket (label) eksik",
          f"{inp_total} form alanının {inp_bad} tanesinin etiketi yok ("
          + ", ".join(f"sayfa {i}" for i, p in zip(idx, pages) if p.get("inputs_without_label")) + ")")
    elif inp_total:
        OK.append("Form alanlarının hepsi etiketli")
    no_vp = [i for i, p in zip(idx, pages) if not p.get("has_viewport")]
    if no_vp:
        f("önemli", "Erişilebilirlik", "Mobil görünüm etiketi (viewport) yok", _pages_str(no_vp, n))
    elif pages:
        OK.append("Mobil görünüm etiketi (viewport) tüm sayfalarda var")

    # ---- Performans (sadece ölçülenler) ----
    slow = [(i, p["elapsed_ms"]) for i, p in zip(idx, pages) if p.get("elapsed_ms", 0) > 800]
    if slow:
        worst = max(ms for _, ms in slow)
        f("önemli" if worst > 1500 else "iyileştirme", "Performans", "Sunucunun HTML yanıtı yavaş",
          ", ".join(f"sayfa {i}: {ms} ms" for i, ms in slow)
          + " (FENIX'ten ölçülen HTML yanıt süresi; tarayıcıdaki tam yükleme süresi değildir)")
    elif pages:
        OK.append(f"Sunucu HTML'i hızlı veriyor (en yavaş sayfa {max(p.get('elapsed_ms', 0) for p in pages)} ms)")
    big = [(i, p["size_kb"]) for i, p in zip(idx, pages) if p.get("size_kb", 0) > 250]
    if big:
        f("iyileştirme", "Performans", "HTML dosyası büyük", ", ".join(f"sayfa {i}: {kb} KB" for i, kb in big))
    many = [(i, p["external_scripts"]) for i, p in zip(idx, pages) if p.get("external_scripts", 0) >= 15]
    if many:
        f("iyileştirme", "Performans", "Çok sayıda harici script",
          ", ".join(f"sayfa {i}: {c} harici script" for i, c in many))
    no_lazy = [i for i, p in zip(idx, pages) if p.get("image_count", 0) >= 10 and not p.get("lazy_images")]
    if no_lazy:
        f("iyileştirme", "Performans", "Çok görselli sayfalarda gecikmeli yükleme (lazy-load) yok", _pages_str(no_lazy, n))

    # ---- İçerik ----
    thin = [i for i, p in zip(idx, pages) if p.get("word_count", 999) < 120 and not p.get("has_password_field")]
    if thin and len(thin) < n:
        f("iyileştirme", "İçerik", "Çok az metin içeren sayfalar", ", ".join(
            f"sayfa {i} (~{pages[i - 1].get('word_count', 0)} kelime)" for i in thin))

    # ---- Türe özel ----
    privacy = any(p.get("privacy_links") for p in pages)
    if kinds & {"eticaret", "uygulama", "egitim"}:
        if privacy:
            OK.append("Gizlilik / KVKK / çerez metnine bağlantı var")
        else:
            f("önemli", "Yasal", "Gizlilik / KVKK / çerez metnine bağlantı bulunamadı",
              "kişisel veri toplayan sitelerde (üyelik, sipariş, form) bu metinler zorunludur")
    if "eticaret" in kinds and "Product" not in schema:
        f("önemli", "SEO", "Ürün işaretlemesi (schema.org Product) yok",
          "ürünlerin fiyatı ve stok durumu arama sonuçlarında görünmez")
    if "uygulama" in kinds and has_login:
        login_idx = has_login[0]
        lp = pages[login_idx - 1]
        if "strict-transport-security" in lp.get("missing_security_headers", []):
            f("önemli", "Güvenlik", "Giriş sayfasında HSTS yok",
              f"sayfa {login_idx}: tarayıcıya 'bu siteye sadece HTTPS ile bağlan' denmiyor")
        if not lp.get("noindex"):
            f("iyileştirme", "SEO", "Giriş sayfası arama motorlarına açık", f"sayfa {login_idx}")
    if kind in ("kurumsal", "egitim") and pages and not any(p.get("has_contact") for p in pages):
        f("önemli", "İçerik", "İletişim bilgisine bağlantı bulunamadı", "telefon, e-posta ya da iletişim sayfası linki yok")

    F.sort(key=lambda x: _SEV_ORDER[x["seviye"]])
    for k, item in enumerate(F, 1):
        item["id"] = f"B{k}"

    not_measured = [
        f"Sadece {n} sayfa tarandı; sitenin geri kalanında farklı durumlar olabilir.",
        "Tarayıcıdaki tam yükleme süresi ve Core Web Vitals (LCP, CLS, INP): FENIX sadece HTML'in sunucu yanıtını ölçer.",
        "Görsellerin dosya boyutu ve formatı: görseller indirilmez.",
        "JavaScript ile sonradan yüklenen içerik, renk kontrastı, klavye ile gezinme.",
        "Arama sıralaması, backlink ve trafik.",
    ]
    if sec.get("dns_hata") and pages:
        not_measured.append("DNS kaydı FENIX'in bilgisayarından sorgulanamadı (site yine de açıldı, yerel bir "
                            "sorgu hatası olabilir; bu bir site sorunu sayılmadı).")
    return F, OK, not_measured


def findings_md(findings, ok, not_measured):
    """Bulguları rapora eklenecek Markdown'a çevirir (sayılar burada, kodda yazılır)."""
    lines = []
    for sev, title in (("kritik", "Kritik"), ("önemli", "Önemli"), ("iyileştirme", "İyileştirme")):
        items = [x for x in findings if x["seviye"] == sev]
        if not items:
            continue
        lines.append(f"### {title} ({len(items)})")
        for x in items:
            lines.append(f"- **{x['id']} · {x['alan']}: {x['baslik']}** — {x['kanit']}")
        lines.append("")
    if not findings:
        lines.append("Ölçülen alanlarda bir sorun bulunmadı.\n")
    out = ["## Bulgular", *lines]
    if ok:
        out += ["## İyi Durumda Olanlar", *[f"- {x}" for x in ok], ""]
    out += ["## Bu Denetimde Ölçülmeyenler", *[f"- {x}" for x in not_measured], ""]
    return "\n".join(out)


def measurement_table_md(pages):
    rows = ["| # | Sayfa | Yanıt (ms) | HTML (KB) | H1 | Meta açıklama | Görsel (alt'sız) | Form alanı (etiketsiz) | Harici script |",
            "|---|---|---|---|---|---|---|---|---|"]
    for i, p in enumerate(pages, 1):
        path = urlparse(p["final_url"]).path or "/"
        if urlparse(p["final_url"]).query:
            path += "?" + urlparse(p["final_url"]).query
        rows.append(f"| {i} | {path[:45]} | {p.get('elapsed_ms', '?')} | {p.get('size_kb', '?')} | {p.get('h1_count', '?')} | "
                    f"{'var' if p.get('meta_description', '(yok)') not in ('(yok)', '') else 'yok'} | "
                    f"{p.get('image_count', 0)} ({p.get('images_without_alt', 0)}) | "
                    f"{p.get('input_count', 0)} ({p.get('inputs_without_label', 0)}) | {p.get('external_scripts', 0)} |")
    return "## Ölçüm Tablosu\n" + "\n".join(rows) + "\n"


# ======================================================================
# ARAŞTIRMA RAPORU
# ======================================================================
RESEARCH_TYPES = {
    "kurum": ("kurum / üniversite / bölüm",
              ["Genel bakış", "Programlar ve eğitim", "Akademik kadro ve araştırma", "Öğrenci olanakları",
               "Öne çıkanlar ve zayıf yönler"],
              "Aday öğrenci ya da veli gözüyle pratik ve doğrulanabilir bilgi ver."),
    "kisi_hesap": ("kişi / sosyal medya hesabı",
                   ["Kim / ne", "Öne çıkan içerik ve faaliyetler", "Kamuoyundaki izlenim"],
                   "Sadece herkese açık bilgileri yaz; özel hayata dair ayrıntı ekleme."),
    "yazilim_sistem": ("yazılım / bilgi sistemi",
                       ["Ne işe yarar", "Özellikler ve modüller", "Kullanıcı deneyimi ve bilinen sorunlar",
                        "Teknik bilgiler"],
                       "Belgelenmiş bilgiyi varsayımdan ayır. Kaynakta dayanağı olmayan teknik öneri (MFA, ELK, "
                       "mikroservis gibi) yazma."),
    "urun": ("ürün / hizmet",
             ["Ürün özeti", "Öne çıkan özellikler", "Artılar", "Eksiler", "Kimler için uygun", "Fiyat ve alternatifler"],
             "Satın alma kararına yardımcı ol; artı ve eksileri kaynaklara dayandır."),
    "karsilastirma": ("karşılaştırma",
                      ["Kısa cevap", "Karşılaştırma", "Hangisi kime uygun"],
                      "Karşılaştırma bölümünde tablo kullan; her hücre kaynaklı olsun."),
    "sirket": ("şirket",
               ["Şirket özeti", "Ürün ve hizmetler", "Çalışma ortamı ve kültür", "Son gelişmeler"],
               "İş başvurusu ya da iş birliği düşünen birinin işine yarayacak bilgiyi öne çıkar."),
    "guncel": ("güncel olay / haber",
               ["Ne oldu", "Zaman çizelgesi", "Tepkiler ve etkiler", "Henüz bilinmeyenler"],
               "Tarihleri net yaz; iddia ile doğrulanmış bilgiyi ayır."),
    "konu": ("genel konu",
             ["Temel bilgiler", "Önemli noktalar", "Farklı görüşler", "Pratik çıkarımlar"],
             "Konuyu anlaşılır ve somut anlat."),
}

WALLED_RE = re.compile(r"\b(instagram|tiktok|facebook|twitter|linkedin|x\.com|threads)\b", re.IGNORECASE)
_CITE_RE = re.compile(r"\[(\d+(?:\s*[,;–-]\s*\d+)*)\]")


def research_type(value, question=""):
    """Plan adımında modelin seçtiği türü doğrular; sosyal medya hesabı sorularını kendisi de tanır."""
    t = (value or "").strip().lower()
    if t not in RESEARCH_TYPES:
        t = "konu"
    if WALLED_RE.search(question or "") and t in ("konu", "kurum"):
        t = "kisi_hesap"
    return t


def _expand(span):
    nums = []
    for part in re.split(r"\s*[,;]\s*", span):
        m = re.match(r"(\d+)\s*[–-]\s*(\d+)$", part)
        if m and int(m.group(2)) - int(m.group(1)) < 50:
            nums += list(range(int(m.group(1)), int(m.group(2)) + 1))
        elif part.strip().isdigit():
            nums.append(int(part))
    return nums


def relevant_sources(notes, n_sources):
    """Notlardan, gerçekten bilgi alınan kaynakları bulur ve numaraları baştan sıralar.
    Döner: (temiz_notlar, eski->yeni numara eşlemesi, kanıtlı madde sayısı).
    'İLGİSİZ [n]' satırları atılır; hiçbir maddede kullanılmayan kaynak rapora girmez."""
    used, facts, kept, seen = [], 0, [], set()
    for block in notes:
        for line in (block or "").splitlines():
            s = line.strip()
            if not s or s.lower() in seen:          # aynı bilgi iki kez sayılmasın
                continue
            seen.add(s.lower())
            if re.search(r"İLGİSİZ|ILGISIZ|ilgisiz", s) and len(s) < 40:
                continue
            nums = [x for m in _CITE_RE.finditer(s) for x in _expand(m.group(1)) if 1 <= x <= n_sources]
            if nums:
                facts += 1
                for x in nums:
                    if x not in used:
                        used.append(x)
            kept.append(s)
    order = sorted(used)
    mapping = {old: new for new, old in enumerate(order, 1)}
    return [renumber(s, mapping) for s in kept], mapping, facts


def renumber(text, mapping):
    """Metindeki [3], [3, 5] atıflarını yeni numaralara çevirir; eşlemede olmayan numaraları siler."""
    def sub(m):
        new = sorted({mapping[x] for x in _expand(m.group(1)) if x in mapping})
        return "[" + ", ".join(str(x) for x in new) + "]" if new else ""
    return _CITE_RE.sub(sub, text)


def weak_result_text(question, n_read, n_relevant, facts_lines, walled, has_direct, kind):
    """Bilgi yetersiz olduğunda rapor yerine verilen açıklama."""
    lines = [f"Bu konuda düzgün bir rapor yazacak kadar bilgi bulamadım. {n_read} sayfa okudum, "
             f"{n_relevant} tanesinde konuyla ilgili bilgi vardı."]
    if facts_lines:
        lines.append("\nBulabildiklerim:")
        lines += [f"- {re.sub(_CITE_RE, '', x).strip(' -•*')}" for x in facts_lines[:5]]
    lines.append("")
    if walled:
        lines.append(f"{walled.capitalize()} giriş istediği için içeriğini doğrudan okuyamıyorum. Profilin ya da "
                     "gönderilerin ekran görüntüsünü atarsan veya metinleri yapıştırırsan oradan değerlendiririm.")
    elif kind == "kurum" and not has_direct:
        lines.append("Kurumun ilgili sayfasının adresini verirsen (ör. bölümün kendi sitesi) doğrudan oradan okurum.")
    else:
        lines.append("Soruyu biraz daraltırsan ya da bir kaynak adresi verirsen tekrar denerim.")
    return "\n".join(lines)
