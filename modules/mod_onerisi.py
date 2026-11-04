# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Mod önerisi (v1.2.1, Mustafa'nın fikri).

İş, seçili moda göre fazla büyükse FENIX cevabın sonunda daha uygun modu önerir ve nedenini söyler:
  • Güvenli modda bilgisayarda değişiklik isteyen bir iş  -> Normal (Güvenli mod sadece okur)
  • Güvenli/Normal modda adım sınırına takılan iş        -> Devil (6 yerine 12 adım)
  • Güvenli/Normal modda araştırma/karşılaştırma isteği  -> Devil (planlı, çok kaynaklı derin araştırma)
  • Güvenli/Normal modda çok uzun, çok parçalı iş        -> Devil
Kullanıcı "evet / olur / dene / geç" derse uygulama o moda geçer ve aynı isteği orada yeniden çalıştırır.
"Hayır" derse aynı öneri bir süre tekrarlanmaz. Mod hiçbir zaman sormadan değişmez.
"""
import re
import time

ETIKET = {"safe": "Güvenli", "normal": "Normal", "devil": "Devil"}
GECERLILIK_SN = 15 * 60          # öneriye bu süre içinde "evet" denirse geçerli
RED_SURESI_SN = 30 * 60          # "hayır" denen mod bu süre boyunca tekrar önerilmez

ONAY_RE = re.compile(r"^\s*(evet|olur|tamam|ok(ey)?|dene|deneyelim|dene bakalım|geç|geçelim|geç ve dene|"
                     r"yap|yapalım|evet geç|evet dene|hadi|tabi(i)?|tabii ki|lütfen)\b[\s.!,]*"
                     r"((devil|normal|güvenli|mod|moda|modunda|moduna|geç|dene|yap|ve|bakalım|lütfen)\b[\s.!,]*){0,4}$",
                     re.IGNORECASE)
RED_RE = re.compile(r"^\s*(hayır|yok|gerek yok|istemiyorum|kalsın|böyle kalsın|geçme)\b", re.IGNORECASE)

EYLEM_RE = re.compile(r"oluştur|yaz\b|yazar mısın|kaydet|sil\b|silebilir|düzenle|değiştir|aç\b|kapat|kur\b|"
                      r"yükle|ayarla|sesi|parlaklı|taşı|yeniden adlandır|gönder", re.IGNORECASE)
YAPAMAM_RE = re.compile(r"bu modda|güvenli mod|yapamam|yapamıyorum|izin(im)? yok|yetkim yok|sadece okuma",
                        re.IGNORECASE)
SINIR_RE = re.compile(r"Adım sınırına ulaşıldı|çok adım sürdü", re.IGNORECASE)
PARCA_RE = re.compile(r"(?m)^\s*(\d{1,2}[.)]|[-•*])\s+\S")


def oner(user_text, mode_key, cevap, calls=(), arastirma_mi=None, reddedilen=None):
    """-> {"mod": hedef, "sebep": "..."} ya da None."""
    if mode_key not in ("safe", "normal"):
        return None
    reddedilen = reddedilen or {}
    t, c = user_text or "", cevap or ""
    engellendi = any(isinstance(r, dict) and "bu modda yapılamaz" in str(r.get("message", "")).lower()
                     for _, _, r in (calls or []))
    adaylar = []
    if mode_key == "safe" and (engellendi or (EYLEM_RE.search(t) and YAPAMAM_RE.search(c))):
        adaylar.append(("normal", "bu iş bilgisayarında değişiklik gerektiriyor; Güvenli mod sadece okur, Normal "
                                  "modda yapar ve riskli adımlarda yine onay sorarım"))
    if SINIR_RE.search(c):
        adaylar.append(("devil", "iş bu modun adım sınırına sığmadı; Devil modda iki kat adım hakkım var"))
    if arastirma_mi is None:
        try:
            from .agent import looks_like_research_command, kendi_belgesi_istegi
            arastirma_mi = looks_like_research_command(t) and not kendi_belgesi_istegi(t)
        except Exception:
            arastirma_mi = False
    if arastirma_mi:
        adaylar.append(("devil", "Devil modda derin araştırma yapıyorum: plan çıkarıp çok sayıda kaynağı okur, "
                                 "kaynaklı bir rapor hazırlarım; burada sadece kısa bir cevap verebildim"))
    simdi = time.time()
    for mod, sebep in adaylar:
        if simdi - reddedilen.get(mod, 0) > RED_SURESI_SN:
            return {"mod": mod, "sebep": sebep}
    return None


def buyuk_is_mi(text):
    return len(text or "") > 700 or len(PARCA_RE.findall(text or "")) >= 6


def on_oneri(user_text, mode_key, reddedilen=None):
    """İşe BAŞLAMADAN sorulacak öneri: açıkça büyük işlerde (uzun, çok parçalı istek) önce sorulur; zayıf bir
    deneme için dakikalarca beklemek ve kota harcamak gerekmez. -> {"mod", "sebep"} ya da None."""
    if mode_key not in ("safe", "normal") or not buyuk_is_mi(user_text):
        return None
    if time.time() - (reddedilen or {}).get("devil", 0) <= RED_SURESI_SN:
        return None
    adim = "6" if mode_key == "normal" else "birkaç"
    return {"mod": "devil", "sebep": f"istek uzun ve çok parçalı; {ETIKET[mode_key]} modda {adim} adım hakkım var ve "
                                     "iş yarım kalabilir, Devil modda iki kat adımla her parçayı tamamlayabilirim"}


def on_soru_metni(oneri, mode_key):
    hedef, simdiki = ETIKET[oneri["mod"]], ETIKET.get(mode_key, mode_key)
    return (f"Başlamadan sorayım: bu işi {hedef} modunda yaparsam daha iyi olur, çünkü {oneri['sebep']}.\n\n"
            f"\"evet\" dersen {hedef} moduna geçip başlarım; \"hayır\" dersen {simdiki} modunda denerim.")


def oneri_metni(oneri):
    return (f"\n\nÖneri: Bu işi {ETIKET[oneri['mod']]} modunda yaparsam daha iyi olur, çünkü {oneri['sebep']}. "
            f"{ETIKET[oneri['mod']]} moduna geçip tekrar deneyeyim mi? (\"evet\" yazman yeterli)")


def onay_mi(text):
    return bool(text) and len(text) <= 40 and bool(ONAY_RE.match(text))


def red_mi(text):
    return bool(text) and len(text) <= 60 and bool(RED_RE.match(text))
