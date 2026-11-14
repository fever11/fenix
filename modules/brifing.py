# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Günlük brifing (v1.4, Mustafa'nın fikri).

Günün İLK açılışında sohbete tek bir mesaj gelir; selamlama saate göredir (bilgisayar akşam açıldıysa "Günaydın"
denmez). Neyin gösterileceğini kullanıcı ilk açılışta seçer, Ayarlar'dan değiştirir:
  • Hava durumu (kullanıcının yazdığı şehir; Open-Meteo, anahtarsız)
  • Bugünkü hatırlatmalar ve kaçırılanlar (yerel)
  • Döviz kurları (Frankfurter / Avrupa Merkez Bankası, anahtarsız)
  • Haber başlıkları (Google Haberler RSS, Türkçe)
Yapay zekâ KULLANILMAZ: Groq kotası harcanmaz, brifing birkaç saniyede gelir. İnternete giden tek bilgi hava için
yazılan şehir adıdır; konum otomatik bulunmaz.
"""
import datetime
import re
import xml.etree.ElementTree as ET

from . import user_settings

ICERIKLER = {"hava": "🌤️ Hava durumu", "hatirlatma": "⏰ Bugünkü hatırlatmalar", "kur": "💱 Döviz kurları",
             "haber": "📰 Haber başlıkları"}
VARSAYILAN = {"acik": True, "icerik": ["hava", "hatirlatma"], "sehir": "", "kurlar": ["USD", "EUR"], "ozel": ""}
ZAMAN_ASIMI = 6
# Sohbette "brifing" / "günün özeti" yazınca (yapay zekâ kullanmadan) brifing gösterilir
KOMUT_RE = re.compile(r"^\s*(brifing(i|imi)?( göster| ver| oku)?|günün özeti(ni)?( göster| ver)?|"
                      r"bugünün özeti(ni)?( ver)?)\s*[.!?]*\s*$", re.IGNORECASE)
HABER_RSS = "https://news.google.com/rss?hl=tr&gl=TR&ceid=TR:tr"

WMO = {0: "açık", 1: "çoğunlukla açık", 2: "parçalı bulutlu", 3: "kapalı", 45: "sisli", 48: "kırağılı sis",
       51: "hafif çiseleme", 53: "çiseleme", 55: "yoğun çiseleme", 56: "dondurucu çiseleme", 57: "dondurucu çiseleme",
       61: "hafif yağmurlu", 63: "yağmurlu", 65: "kuvvetli yağmurlu", 66: "dondurucu yağmur", 67: "dondurucu yağmur",
       71: "hafif karlı", 73: "karlı", 75: "yoğun karlı", 77: "kar taneli", 80: "hafif sağanak", 81: "sağanak",
       82: "kuvvetli sağanak", 85: "kar sağanağı", 86: "yoğun kar sağanağı", 95: "gök gürültülü fırtına",
       96: "dolulu fırtına", 99: "kuvvetli dolulu fırtına"}


# ------------------------------------------------------------------ ayarlar
def ayarlar():
    a = dict(VARSAYILAN)
    a.update(user_settings.get("brifing", {}) or {})
    a["icerik"] = [i for i in a.get("icerik", []) if i in ICERIKLER]
    return a


def ayarlandi_mi():
    return bool(user_settings.get("brifing"))


def kaydet(**kw):
    a = ayarlar()
    a.update(kw)
    user_settings.set("brifing", a)


def gerekli_mi(bugun=None):
    """Brifing açık ve bugün henüz gösterilmediyse True."""
    bugun = (bugun or datetime.date.today()).isoformat()
    a = ayarlar()
    return (ayarlandi_mi() and a.get("acik") and (bool(a.get("icerik")) or bool((a.get("ozel") or "").strip()))
            and user_settings.get("brifing_son_gun") != bugun)


def gosterildi(bugun=None):
    user_settings.set("brifing_son_gun", (bugun or datetime.date.today()).isoformat())


def selamlama(saat):
    if 5 <= saat < 11:
        return "Günaydın"
    if 11 <= saat < 17:
        return "İyi günler"
    if 17 <= saat < 22:
        return "İyi akşamlar"
    return "İyi geceler"


# ------------------------------------------------------------------ veri kaynakları (hepsi hata toleranslı)
def _get(url, **params):
    import requests
    r = requests.get(url, params=params or None, timeout=ZAMAN_ASIMI, headers={"User-Agent": "FENIX-brifing"})
    r.raise_for_status()
    return r


def sehirleri_ayir(metin):
    """'Bartın, Bilecik' / 'Bartın ve Bilecik' / 'Bartın; Bilecik' -> ['Bartın', 'Bilecik']"""
    parcalar = re.split(r"\s*(?:,|;|/|\bve\b|\n)\s*", metin or "")
    return [p.strip() for p in parcalar if p.strip()]


def ozel_istek_metni():
    """Kullanıcının serbest yazdığı brifing istekleri için yapay zekâya gidecek istek (boşsa None)."""
    ozel = (ayarlar().get("ozel") or "").strip()
    if not ozel:
        return None
    return ("Günlük brifingim için şu konularda kısa ve güncel bilgi ver (gerekiyorsa internette ara, her konu en "
            "fazla 2 cümle, varsa kaynağını yaz, uydurma): " + ozel)


def hava(sehir, getir=None):
    """-> 'Bartın: parçalı bulutlu, 9–16 °C, yağış ihtimali %40' ya da None."""
    if not (sehir or "").strip():
        return None
    getir = getir or (lambda url, **p: _get(url, **p).json())
    try:
        g = getir("https://geocoding-api.open-meteo.com/v1/search", name=sehir.strip(), count=1, language="tr")
        yer = (g.get("results") or [None])[0]
        if not yer:
            return f"'{sehir}' adında bir yer bulamadım; Ayarlar > Brifing'den şehri düzeltebilirsin."
        d = getir("https://api.open-meteo.com/v1/forecast", latitude=yer["latitude"], longitude=yer["longitude"],
                  daily="weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                  current_weather="true", timezone="auto", forecast_days=1)
        gun = d["daily"]
        durum = WMO.get(int(gun["weathercode"][0]), "")
        enaz, encok = round(gun["temperature_2m_min"][0]), round(gun["temperature_2m_max"][0])
        yagis = gun.get("precipitation_probability_max", [None])[0]
        simdi = (d.get("current_weather") or {}).get("temperature")
        metin = f"{yer.get('name', sehir)}: {durum}, {enaz}–{encok} °C"
        if simdi is not None:
            metin += f" (şu an {round(simdi)} °C)"
        if yagis is not None:
            metin += f", yağış ihtimali %{yagis}"
            if yagis >= 50:
                metin += " — şemsiyeni al"
        return metin
    except Exception as e:
        print(f"[BRİFİNG] hava alınamadı: {e}")
        return None


def _kur_coz(d, hedef="TRY"):
    """Frankfurter cevabından kuru bulur (v2 tek çift: {'rate': x}; v1: {'rates': {'TRY': x}}; liste)."""
    if isinstance(d, list):
        d = d[0] if d else {}
    if not isinstance(d, dict):
        return None
    for anahtar in ("rate", "value", "mid"):
        if isinstance(d.get(anahtar), (int, float)):
            return float(d[anahtar])
    r = d.get("rates") or d.get("quotes")
    if isinstance(r, dict):
        v = r.get(hedef) or r.get(hedef.lower())
        return float(v) if isinstance(v, (int, float)) else None
    if isinstance(r, list) and r:
        return _kur_coz(r[0], hedef)
    return None


def kurlar(semboller=("USD", "EUR"), getir=None):
    """-> '1 USD = 34,52 TL · 1 EUR = 37,10 TL' ya da None (Frankfurter: merkez bankası günlük kurları)."""
    getir = getir or (lambda url, **p: _get(url, **p).json())
    parcalar = []
    for s in semboller:
        tl = None
        for url, p in ((f"https://api.frankfurter.dev/v2/rate/{s.lower()}/try", {}),
                       ("https://api.frankfurter.dev/v1/latest", {"base": s, "symbols": "TRY"})):
            try:
                tl = _kur_coz(getir(url, **p))
            except Exception as e:
                print(f"[BRİFİNG] {s} kuru alınamadı ({url}): {e}")
            if tl:
                break
        if tl:
            parcalar.append(f"1 {s} = {tl:.2f} TL".replace(".", ","))
    return " · ".join(parcalar) or None


def haberler(n=3, getir=None):
    """Google Haberler (Türkiye) ilk başlıklar."""
    getir = getir or (lambda url: _get(url).text)
    try:
        kok = ET.fromstring(getir(HABER_RSS))
        basliklar = []
        for item in kok.iter("item"):
            t = (item.findtext("title") or "").strip()
            t = re.sub(r"\s+-\s+[^-]{2,40}$", "", t)          # sondaki " - Kaynak adı"
            if t and t not in basliklar:
                basliklar.append(t)
            if len(basliklar) >= n:
                break
        return basliklar or None
    except Exception as e:
        print(f"[BRİFİNG] haberler alınamadı: {e}")
        return None


def hatirlatmalar(store, simdi=None):
    """-> (bugünkü bekleyenler, kaçırılanlar)."""
    simdi = simdi or datetime.datetime.now()
    gun_basi = simdi.replace(hour=0, minute=0, second=0, microsecond=0)
    gun_sonu = gun_basi + datetime.timedelta(days=1)
    try:
        bekleyen = store.pending()
    except Exception:
        return [], []
    bugun = [r for r in bekleyen if gun_basi <= r["due"] < gun_sonu]
    kacan = [r for r in bekleyen if r["due"] < gun_basi]
    return bugun, kacan


# ------------------------------------------------------------------ brifing metni
def olustur(store=None, simdi=None, ad=None, kaynaklar=None):
    """Brifing metni. kaynaklar: test için {'hava': fn, 'kur': fn, 'haber': fn}."""
    simdi = simdi or datetime.datetime.now()
    a = ayarlar()
    k = kaynaklar or {}
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
             "Aralık"]
    bas = f"{selamlama(simdi.hour)}{' ' + ad if ad else ''}! Bugün {simdi.day} {aylar[simdi.month - 1]} " \
          f"{gunler[simdi.weekday()]}."
    satirlar = [bas]
    if "hava" in a["icerik"]:
        sehirler = sehirleri_ayir(a.get("sehir"))
        if sehirler:
            # 14.11: "Bartın, Bilecik" tek bir yer gibi aranıp bulunamamıştı; her şehir ayrı sorulur
            for sh in sehirler[:4]:
                h = (k.get("hava") or hava)(sh)
                satirlar.append(f"🌤️ {h}" if h else f"🌤️ {sh}: hava durumuna şu an ulaşamadım.")
        else:
            satirlar.append("🌤️ Hava için şehir seçilmemiş (Ayarlar > Brifing).")
    if "hatirlatma" in a["icerik"] and store is not None:
        bugun, kacan = hatirlatmalar(store, simdi)
        if bugun:
            satirlar.append("⏰ Bugün: " + "; ".join(f"{r['due']:%H:%M} {r['text']}" for r in bugun[:6]))
        else:
            satirlar.append("⏰ Bugün için hatırlatma yok.")
        if kacan:
            satirlar.append("⚠️ Kaçırılan: " + "; ".join(f"{r['due']:%d.%m %H:%M} {r['text']}" for r in kacan[:4]))
    if "kur" in a["icerik"]:
        kr = (k.get("kur") or kurlar)(a.get("kurlar") or ["USD", "EUR"])
        satirlar.append(f"💱 {kr}" if kr else "💱 Kurlara şu an ulaşamadım.")
    if "haber" in a["icerik"]:
        hb = (k.get("haber") or haberler)()
        if hb:
            satirlar.append("📰 Öne çıkanlar:\n" + "\n".join(f"  • {b}" for b in hb))
    return "\n".join(satirlar)


# ------------------------------------------------------------------ ilk açılış / ayar penceresi
def ayar_penceresi(app, ctk, kaydedince=None, renk="#38bdf8"):
    """Brifingde neler gösterilsin? İlk açılışta bir kez, sonra Ayarlar'dan açılır."""
    a = ayarlar()
    w = ctk.CTkToplevel(app)
    w.title("FENIX • Günlük brifing")
    w.geometry("440x640")
    w.configure(fg_color="#04070d")
    w.transient(app)
    ctk.CTkLabel(w, text="Günlük brifing", font=("Segoe UI", 17, "bold"), text_color=renk).pack(
        anchor="w", padx=18, pady=(16, 2))
    ctk.CTkLabel(w, text="Günün ilk açılışında sohbete kısa bir özet gelir. Selamlama saate göredir. Yapay zekâ "
                         "kullanılmaz, kota harcamaz.", wraplength=400, justify="left", text_color="#8aa0b6",
                 font=("Segoe UI", 12)).pack(anchor="w", padx=18)
    acik = ctk.CTkSwitch(w, text="Brifing açık", font=("Segoe UI", 12), progress_color=renk)
    if a.get("acik", True):
        acik.select()
    acik.pack(anchor="w", padx=18, pady=(12, 6))
    secim = {}
    for anahtar, yazi in ICERIKLER.items():
        cb = ctk.CTkCheckBox(w, text=yazi, font=("Segoe UI", 12), fg_color=renk)
        if anahtar in a["icerik"]:
            cb.select()
        cb.pack(anchor="w", padx=30, pady=3)
        secim[anahtar] = cb
    ctk.CTkLabel(w, text="Hava durumu için şehir (ör. Bartın):", font=("Segoe UI", 12), text_color="#dbe7f3").pack(
        anchor="w", padx=18, pady=(12, 2))
    sehir = ctk.CTkEntry(w, width=260)
    sehir.insert(0, a.get("sehir", ""))
    sehir.pack(anchor="w", padx=18)
    ctk.CTkLabel(w, text="Birden fazla şehir için virgülle ayır (Bartın, Bilecik). Şehir adları sadece hava durumu "
                         "için Open-Meteo'ya gönderilir.", wraplength=400, justify="left", text_color="#8aa0b6",
                 font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(2, 0))
    ctk.CTkLabel(w, text="Ayrıca her gün bilgi almak istediklerin (serbest yaz):", font=("Segoe UI", 12),
                 text_color="#dbe7f3").pack(anchor="w", padx=18, pady=(12, 2))
    ozel = ctk.CTkTextbox(w, height=70, width=400, fg_color="#0b1522", text_color="#dbe7f3", font=("Segoe UI", 12))
    ozel.insert("1.0", a.get("ozel", ""))
    ozel.pack(anchor="w", padx=18)
    ctk.CTkLabel(w, text="Örn: Galatasaray'ın son maçı, Bitcoin fiyatı, yapay zekâ haberleri. Bu kısım yapay zekâ ve "
                         "internet araması kullanır (Groq kotasından yer); boş bırakırsan kullanılmaz.", wraplength=400,
                 justify="left", text_color="#8aa0b6", font=("Segoe UI", 10)).pack(anchor="w", padx=18, pady=(2, 0))

    def kaydet_ve_kapat():
        kaydet(acik=bool(acik.get()), icerik=[k for k, cb in secim.items() if cb.get()], sehir=sehir.get().strip(),
               ozel=ozel.get("1.0", "end").strip()[:500])
        w.destroy()
        if kaydedince:
            kaydedince()
    ctk.CTkButton(w, text="Kaydet", command=kaydet_ve_kapat, fg_color=renk, text_color="#001018").pack(
        anchor="e", padx=18, pady=16, side="bottom")
    w.protocol("WM_DELETE_WINDOW", kaydet_ve_kapat)
    w.after(80, lambda: (w.lift(), w.focus_force()))
    return w
