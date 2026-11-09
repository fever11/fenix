# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Güncelleme bildirimi (v1.2.2).

FENIX, resmi depodaki (github.com/fever11/fenix) en son SÜRÜMÜ (GitHub Releases) arka planda denetler; kullanıcının
sürümü daha eskiyse küçük, kapatılabilir bir bildirim gösterir.

Neden commit değil, sürüm (release)? Her commit kullanıcıya hazır bir güncelleme değildir (yarım iş, test, belge
düzeltmesi olabilir); her push'ta bildirim gelmesi rahatsız eder. Yayımlanan sürüm "kurulmaya hazır" demektir.

Güvenlik ve gizlilik:
  • Sadece okuma: GitHub'ın herkese açık API'sine kimliksiz bir GET isteği gider; kullanıcıya ait hiçbir bilgi
    gönderilmez (istek başlığında genel bir program adı vardır, e-posta/anahtar yoktur).
  • FENIX hiçbir şeyi kendiliğinden İNDİRMEZ ya da ÇALIŞTIRMAZ: bildirimdeki düğme yalnızca resmi sürüm sayfasını
    tarayıcıda açar. Sayfa adresi resmi depoya ait değilse hiç gösterilmez.
  • En fazla 6 saatte bir denetlenir (GitHub'ın kimliksiz istek sınırı: saatte 60).
  • Ayarlar'dan kapatılabilir; "Bu sürümü atla" denen sürüm bir daha bildirilmez.
"""
import json
import os
import re
import threading
import time

from .version import VERSION
from . import user_settings

DEPO = "fever11/fenix"
API = f"https://api.github.com/repos/{DEPO}/releases/latest"
RESMI_SAYFA = f"https://github.com/{DEPO}/releases"
DURUM = os.path.join("data", "guncelleme.json")
ARALIK_SN = 6 * 3600
ZAMAN_ASIMI = 8


def surum_tuple(metin):
    """'v1.2.10' -> (1, 2, 10). Ön sürüm etiketleri ('-beta') yok sayılır; çözülemezse None."""
    m = re.match(r"\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(metin or ""))
    if not m:
        return None
    return tuple(int(x or 0) for x in m.groups())


def daha_yeni_mi(uzak, yerel=VERSION):
    u, y = surum_tuple(uzak), surum_tuple(yerel)
    return bool(u and y and u > y)


def guvenli_adres(url):
    """Bildirimde yalnızca resmi depodaki sayfalar açılır."""
    return isinstance(url, str) and url.startswith(f"https://github.com/{DEPO}/")


def _durum_oku():
    try:
        with open(DURUM, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _durum_yaz(d):
    try:
        os.makedirs(os.path.dirname(DURUM), exist_ok=True)
        with open(DURUM, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def acik():
    return bool(user_settings.get("guncelleme_denetle", True))


def atla(etiket):
    """'Bu sürümü atla': bu sürüm bir daha bildirilmez (daha yenisi çıkarsa bildirilir)."""
    d = _durum_oku()
    d["atlanan"] = etiket
    _durum_yaz(d)


def _cozumle(veri, yerel=None):
    """GitHub 'latest release' cevabından sürüm bilgisini çıkarır. yerel verilirse sadece daha yeniyse döner."""
    if not isinstance(veri, dict) or veri.get("draft") or veri.get("prerelease"):
        return None
    etiket = str(veri.get("tag_name") or "").strip()
    if not etiket or not surum_tuple(etiket) or (yerel is not None and not daha_yeni_mi(etiket, yerel)):
        return None
    sayfa = veri.get("html_url")
    if not guvenli_adres(sayfa):
        sayfa = RESMI_SAYFA
    # Özet: notlardaki madde satırları (başlık "##" ve uyarı ">" satırları değil). 09.11 denemesinde özete
    # "Sadece Windows 10 ve 11" uyarısı girmiş, asıl yenilikler görünmemişti.
    satirlar = []
    for ham in str(veri.get("body") or "").splitlines():
        st = ham.strip()
        if st.startswith("#") and satirlar:
            break                                   # sadece ilk bölüm (ör. Türkçe "Yenilikler"); çeviri tekrar etmez
        if not re.match(r"^[-*•]\s+", st):
            continue
        st = re.sub(r"^[-*•]\s+", "", st)
        st = re.sub(r"\*\*([^*]+)\*\*", r"\1", st)
        st = re.sub(r"[*_`]+", "", st).strip()
        st = st.split(":")[0].strip() if ":" in st[:40] else st.split(".")[0].strip()   # kısa başlık kısmı
        if st and st not in satirlar:
            satirlar.append(st)
    return {"etiket": etiket, "surum": etiket.lstrip("vV"), "ad": str(veri.get("name") or etiket)[:80],
            "sayfa": sayfa, "ozet": " · ".join(satirlar[:3])[:240]}


def denetle(zorla=False, getir=None):
    """Yeni sürüm varsa bilgi sözlüğü, yoksa None. Ağ hatası sessizce yutulur (bildirim çıkmaz).
    getir: test için sahte istek fonksiyonu (url -> sözlük)."""
    if not zorla and not acik():
        return None
    d = _durum_oku()
    simdi = time.time()
    if not zorla and simdi - d.get("son_denetim", 0) < ARALIK_SN:
        bilgi = d.get("son_bulunan")                     # sınır içinde: son bulunan bilgi yeniden kullanılır
    else:
        try:
            if getir is None:
                import requests
                r = requests.get(API, timeout=ZAMAN_ASIMI,
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": "FENIX-guncelleme-denetimi"})
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                veri = r.json()
            else:
                veri = getir(API)
            bilgi = _cozumle(veri)
        except Exception as e:
            print(f"[GÜNCELLEME] denetlenemedi: {e}")
            d["son_denetim"] = simdi                    # ağ yoksa sürekli denemesin
            _durum_yaz(d)
            return None
        d.update(son_denetim=simdi, son_bulunan=bilgi)
        _durum_yaz(d)
    # Önbellekte yerel sürümden bağımsız olarak depodaki son sürüm tutulur; karşılaştırma her seferinde yapılır
    # (09.11: 1.2.2'de açılıp sonra sürüm 1.2.1'e alınınca 'yeni yok' sonucu 6 saat önbellekte kalıyordu).
    if not bilgi or not daha_yeni_mi(bilgi.get("etiket"), VERSION) or d.get("atlanan") == bilgi.get("etiket"):
        return None
    return bilgi


def arka_planda(geri_cagir, gecikme=20):
    """Uygulama açıldıktan sonra arka planda denetler; yeni sürüm varsa geri_cagir(bilgi) çağrılır.
    Sonra 6 saatte bir tekrarlar (uygulama uzun süre açık kalırsa)."""
    def calis():
        time.sleep(gecikme)
        while True:
            try:
                bilgi = denetle()
                if bilgi:
                    geri_cagir(bilgi)
            except Exception as e:
                print(f"[GÜNCELLEME] {e}")
            time.sleep(ARALIK_SN)
    t = threading.Thread(target=calis, daemon=True, name="guncelleme")
    t.start()
    return t
