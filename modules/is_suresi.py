# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""İş türüne göre süre tahmini (v1.2.3, Mustafa'nın fikri).

Her iş aynı sürede bitmez: "selam" birkaç saniye, hava durumu araması yarım dakika, kod yazıp denemek ya da rapor
hazırlamak birkaç dakika sürer. Tek bir sabit süre sınırı ya kısa işleri gereksiz bekletir ya da uzun işleri yarıda
keser. Bu modül:
  • isteğin türünü bulur (sohbet, hesap, güncel bilgi, bilgisayar işi, dosya, kod, belge, araştırma),
  • o türdeki işlerin bu bilgisayarda gerçekte ne kadar sürdüğünü öğrenir (son 30 başarılı işin ortancası),
  • tahmini süreyi ve bu tahmine göre esneyen bir üst sınırı verir.
Üst sınır yine de vardır: 13.11'de bir arkadaşın "selam" mesajına 15 dk sonra cevap geldi (kota dolunca yedek modeller
uzun zaman aşımlarıyla tek tek deneniyordu). Sınır tahmine göre belirlenir; o türün tavanını geçmez.
"""
import json
import os
import re
import statistics

DOSYA = os.path.join("data", "is_sureleri.json")
SAKLA = 30          # tür başına saklanan son süre sayısı
EN_AZ_ORNEK = 3     # bundan az ölçüm varsa varsayılan tahmin kullanılır

# tür: (etiket, varsayılan tahmin sn, sınırın tavanı sn)
TURLER = {
    "sohbet":     ("Sohbet", 8, 120),
    "hesap":      ("Hesap", 10, 120),
    "guncel":     ("Güncel bilgi (internet araması)", 35, 240),
    "bilgisayar": ("Bilgisayar işi", 20, 180),
    "dosya":      ("Dosya işi", 25, 240),
    "kod":        ("Kod yazma / deneme", 90, 600),
    "belge":      ("Belge / rapor", 120, 600),
    "arastirma":  ("Araştırma", 180, 900),
}
CARPAN = 4           # sınır = tahmin × 4 (yavaş bir günde de iş bitebilsin)
EN_KISA_SINIR = 90   # hiçbir iş 90 sn'den önce kesilmez
DEVIL_CARPANI = 1.5  # Devil modu daha çok adım atar: tavan 1,5 kat

_KOD = re.compile(r"\bkod(u|unu|la)?\b|script|betik|program yaz|fonksiyon|\bpython\b|\.py\b|\bjava\b|javascript|"
                  r"\bjs\b|\bc#|\bhtml\b|\bcss\b|test et|derle|hata ayıkla|debug|algoritma", re.IGNORECASE)
_BELGE = re.compile(r"rapor|belge|word|\bpdf\b|docx|makale|ödev(imi)? yaz|sunum|özgeçmiş|\bcv\b|dilekçe|"
                    r"günü özetle", re.IGNORECASE)
_DOSYA = re.compile(r"dosya|klasör|klasor|masaüst|masaust|\.(txt|md|csv|json|xlsx?)\b|kaydet|içinde ne yazıyor",
                    re.IGNORECASE)
_BILGISAYAR = re.compile(r"\baç\b|kapat|sesi|\bses(i|ini)? |parlaklı|wi-?fi|bluetooth|hatırlat|uygulama|pencere|"
                         r"ekran görüntüsü|ekrana bak|kısayol", re.IGNORECASE)
_HESAP = re.compile(r"\d\s*[-+*/x×÷%^]\s*\d|%\s*\d|\d\s*%|yüzde|indirim|faiz|taksit|kaç eder|hesapla|kaç (dakika|saniye|saat|gün|"
                    r"derece|metre|km|kilo|gram|litre)|dönüştür|çevir.*(birim|derece)", re.IGNORECASE)


def hesap_mi(metin):
    """Eldeki sayılarla yapılacak bir hesap mı? ("1250 TL'ye %18 indirim kaç TL olur" internette aranmaz.)"""
    return bool(_HESAP.search(metin or ""))


def tur_bul(metin, mode_key=None):
    """İsteğin türü (TURLER anahtarı)."""
    t = metin or ""
    try:
        from .mod_onerisi import ARASTIRMA_RE
        if ARASTIRMA_RE.search(t):
            return "arastirma"
    except Exception:
        pass
    if _KOD.search(t):
        return "kod"
    if _BELGE.search(t):
        return "belge"
    if hesap_mi(t):
        return "hesap"
    try:
        from .llm_client import LLMClient
        if LLMClient._GUNCEL_RE.search(t):
            return "guncel"
    except Exception:
        pass
    if _DOSYA.search(t):
        return "dosya"
    if _BILGISAYAR.search(t):
        return "bilgisayar"
    if _HESAP.search(t):
        return "hesap"
    return "sohbet"


def _oku():
    try:
        with open(DOSYA, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _yaz(d):
    try:
        os.makedirs(os.path.dirname(DOSYA), exist_ok=True)
        with open(DOSYA, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def kaydet(tur, sure):
    """Başarıyla biten bir işin süresini öğrenir (durdurulan ya da hata veren işler kaydedilmez)."""
    if tur not in TURLER or not isinstance(sure, (int, float)) or sure <= 0:
        return
    d = _oku()
    liste = [x for x in d.get(tur, []) if isinstance(x, (int, float))]
    liste.append(round(float(sure), 1))
    d[tur] = liste[-SAKLA:]
    _yaz(d)


def tahmin(tur):
    """Bu türdeki işin tahmini süresi (sn): yeterli ölçüm varsa ortanca, yoksa varsayılan."""
    varsayilan = TURLER.get(tur, TURLER["sohbet"])[1]
    olcumler = [x for x in _oku().get(tur, []) if isinstance(x, (int, float))]
    if len(olcumler) < EN_AZ_ORNEK:
        return varsayilan
    return max(2.0, statistics.median(olcumler))


def sinir(tur, mode_key=None):
    """Bu iş en fazla ne kadar sürebilir (sn): tahmine göre esner, türün tavanını geçmez."""
    tavan = TURLER.get(tur, TURLER["sohbet"])[2] * (DEVIL_CARPANI if mode_key == "devil" else 1)
    return int(min(tavan, max(EN_KISA_SINIR, tahmin(tur) * CARPAN)))


def sure_metni(sn):
    sn = int(round(sn))
    if sn < 60:
        return f"{sn} sn"
    return f"{sn // 60} dk" + (f" {sn % 60} sn" if sn % 60 else "")


def plan(metin, mode_key=None, tur=None):
    """-> {"tur", "etiket", "tahmin", "sinir"}"""
    tur = tur if tur in TURLER else tur_bul(metin, mode_key)
    return {"tur": tur, "etiket": TURLER[tur][0], "tahmin": tahmin(tur), "sinir": sinir(tur, mode_key)}
