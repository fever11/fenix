# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""İşlem defteri ve geri alma (v1.4, Mustafa'nın fikri).

FENIX'in bilgisayarda yaptığı her değişiklik (dosya yazma, düzenleme, silme, komut, başlangıçtan kaldırma) tek satır
olarak data/islem_defteri.jsonl dosyasına yazılır. Kullanıcı "bugün ne yaptın?" diye sorabilir, "son yaptığını geri
al" diyebilir ya da defteri açıp istediği satırı geri alabilir.

FENIX çöp kutusu: FENIX'in sildiği dosyalar Windows Geri Dönüşüm Kutusu yerine data/cop klasörüne taşınır (Geri
Dönüşüm Kutusu dolunca kendini boşaltabilir; burada geri alma her zaman çalışır). 30 günü dolanlar FENIX açılışında
kalıcı silinir. Bu kural SADECE FENIX'in sildiği dosyalara uygulanır; kullanıcının kendi dosyalarına dokunulmaz.
Dosya FENIX'ten farklı bir sürücüdeyse (taşıma uzun süren bir kopyalama olurdu) Geri Dönüşüm Kutusu kullanılır.

Yük: her işlem için tek satır (birkaç yüz bayt) yazılır; yapay zekâ kullanılmaz, kotaya dokunmaz.
"""
import json
import os
import shutil
import threading
import time
import uuid

DEFTER = os.path.join("data", "islem_defteri.jsonl")
COP = os.path.join("data", "cop")
SAKLAMA_GUN = 30
_KILIT = threading.Lock()

TUR_ADI = {"olusturma": "Dosya oluşturma", "uzerine_yazma": "Üzerine yazma", "duzenleme": "Düzenleme",
           "silme": "Silme", "komut": "Komut", "baslangic": "Açılıştan kaldırma", "geri_alma": "Geri alma"}


def _simdi():
    return time.time()


def _yaz(kayit):
    with _KILIT:
        os.makedirs(os.path.dirname(DEFTER), exist_ok=True)
        with open(DEFTER, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def kaydet(tur, ozet, yol="", geri=None):
    """Bir işlemi deftere yazar. geri: geri almak için gereken bilgi (None = geri alınamaz). -> kayıt kimliği"""
    k = {"id": uuid.uuid4().hex[:8], "zaman": round(_simdi(), 1), "tur": tur, "ozet": str(ozet)[:300],
         "yol": yol or "", "geri": geri}
    try:
        _yaz(k)
    except Exception as e:
        print(f"[DEFTER] yazılamadı: {e}")
    return k["id"]


def oku():
    """Tüm kayıtlar (eskiden yeniye). Her kayda 'geri_alindi' alanı eklenir."""
    kayitlar = []
    try:
        with open(DEFTER, encoding="utf-8") as f:
            for satir in f:
                try:
                    kayitlar.append(json.loads(satir))
                except Exception:
                    continue
    except FileNotFoundError:
        return []
    except Exception:
        return []
    geri_alinan = {k.get("hedef") for k in kayitlar if k.get("tur") == "geri_alma"}
    for k in kayitlar:
        k["geri_alindi"] = k.get("id") in geri_alinan
    return kayitlar


def _ayni_surucu(a, b):
    try:
        return os.path.splitdrive(os.path.abspath(a))[0].lower() == os.path.splitdrive(os.path.abspath(b))[0].lower()
    except Exception:
        return False


def cope_tasi(yol):
    """Dosya/klasörü FENIX çöp kutusuna taşır. -> çöpteki yol; farklı sürücüdeyse None (çağıran Geri Dönüşüm
    Kutusu'nu kullanır)."""
    yol = os.path.abspath(yol)
    if not _ayni_surucu(yol, COP):
        return None
    hedef_klasor = os.path.abspath(os.path.join(COP, f"{int(_simdi())}_{uuid.uuid4().hex[:6]}"))
    os.makedirs(hedef_klasor, exist_ok=True)
    hedef = os.path.join(hedef_klasor, os.path.basename(yol.rstrip("\\/")) or "oge")
    shutil.move(yol, hedef)
    return hedef


def cope_kopyala(yol):
    """Üzerine yazılacak dosyanın eski hâlini çöpe KOPYALAR (geri almak için). -> kopyanın yolu ya da None"""
    try:
        yol = os.path.abspath(yol)
        hedef_klasor = os.path.abspath(os.path.join(COP, f"{int(_simdi())}_{uuid.uuid4().hex[:6]}"))
        os.makedirs(hedef_klasor, exist_ok=True)
        hedef = os.path.join(hedef_klasor, os.path.basename(yol))
        shutil.copy2(yol, hedef)
        return hedef
    except Exception as e:
        print(f"[DEFTER] yedek alınamadı: {e}")
        return None


def _geri_alinabilir(k):
    return bool(k.get("geri")) and not k.get("geri_alindi") and k.get("tur") != "geri_alma"


def son_geri_alinabilir():
    for k in reversed(oku()):
        if _geri_alinabilir(k):
            return k
    return None


def bul(kayit_id):
    for k in oku():
        if k.get("id") == kayit_id:
            return k
    return None


def geri_al(kayit_id=None, onayla=None):
    """Bir işlemi geri alır (kimlik verilmezse geri alınabilir son işlemi). onayla(baslik, mesaj) -> bool.
    Var olan bir dosyanın üzerine asla yazmaz; çakışma varsa geri almaz ve nedenini söyler."""
    k = bul(kayit_id) if kayit_id else son_geri_alinabilir()
    if not k:
        return {"status": "error", "message": ("Geri alınabilecek bir işlem bulamadım." if not kayit_id else
                                               f"'{kayit_id}' numaralı işlemi defterde bulamadım.")}
    if k.get("geri_alindi"):
        return {"status": "error", "message": "Bu işlem zaten geri alınmış."}
    g = k.get("geri") or {}
    if not g:
        return {"status": "error", "message": f"Bu işlem geri alınamaz: {k.get('ozet')}"}
    tarif = {"copten_geri": f"'{os.path.basename(g.get('yol', ''))}' eski yerine geri konacak.",
             "olusturulani_kaldir": f"FENIX'in oluşturduğu '{os.path.basename(g.get('yol', ''))}' çöp kutusuna "
                                    "taşınacak.",
             "yedekten_geri": f"'{os.path.basename(g.get('yol', ''))}' değişiklikten önceki hâline döndürülecek.",
             "baslangic": f"'{g.get('ad')}' yeniden açılışta başlayacak."}.get(g.get("islem"), "")
    if onayla and not onayla("İşlem geri alınacak", f"{TUR_ADI.get(k['tur'], k['tur'])}: {k.get('ozet')}\n\n{tarif}"):
        return {"status": "cancelled", "message": "Geri almadım."}
    try:
        sonuc = _uygula(g)
    except Exception as e:
        return {"status": "error", "message": f"Geri alamadım: {e}"}
    if sonuc.get("status") == "ok":
        kaydet("geri_alma", f"Geri alındı: {k.get('ozet')}", k.get("yol"), None)
        _hedef_isaretle(k["id"])
    return sonuc


def _hedef_isaretle(kayit_id):
    # Son eklenen 'geri_alma' kaydına hangi işlemi geri aldığını yaz (append-only defterde eşleme)
    with _KILIT:
        try:
            with open(DEFTER, encoding="utf-8") as f:
                satirlar = f.read().splitlines()
            son = json.loads(satirlar[-1])
            son["hedef"] = kayit_id
            satirlar[-1] = json.dumps(son, ensure_ascii=False)
            with open(DEFTER, "w", encoding="utf-8") as f:
                f.write("\n".join(satirlar) + "\n")
        except Exception as e:
            print(f"[DEFTER] işaretlenemedi: {e}")


def _uygula(g):
    islem = g.get("islem")
    if islem == "copten_geri":
        kaynak, yol = g.get("cop"), g.get("yol")
        if not kaynak or not os.path.exists(kaynak):
            return {"status": "error", "message": "Çöp kutusundaki kopya artık yok (30 gün dolmuş ya da silinmiş)."}
        if os.path.exists(yol):
            return {"status": "error", "message": f"'{yol}' konumunda şu an başka bir dosya var; üzerine yazmadım."}
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        shutil.move(kaynak, yol)
        _bos_klasoru_sil(os.path.dirname(kaynak))
        return {"status": "ok", "message": f"'{os.path.basename(yol)}' eski yerine geri kondu.", "yol": yol}
    if islem == "olusturulani_kaldir":
        yol = g.get("yol")
        if not os.path.exists(yol):
            return {"status": "error", "message": "Bu dosya zaten yok."}
        hedef = cope_tasi(yol)
        if not hedef:
            return {"status": "error", "message": "Dosya başka bir sürücüde; çöp kutusuna taşıyamadım."}
        return {"status": "ok", "message": f"'{os.path.basename(yol)}' kaldırıldı (FENIX çöp kutusunda "
                                           f"{SAKLAMA_GUN} gün durur).", "yol": yol}
    if islem == "yedekten_geri":
        yedek, yol = g.get("yedek"), g.get("yol")
        if not yedek or not os.path.exists(yedek):
            return {"status": "error", "message": "Değişiklikten önceki yedek artık yok."}
        if os.path.exists(yol):
            cope_kopyala(yol)                    # şimdiki hâli de kaybolmasın (çöpte 30 gün durur)
        shutil.copy2(yedek, yol)
        return {"status": "ok", "message": f"'{os.path.basename(yol)}' önceki hâline döndü.", "yol": yol}
    if islem == "baslangic":
        from . import functions as fx
        return fx.restore_startup_program(g.get("ad", ""))
    return {"status": "error", "message": "Bu işlem türü geri alınamıyor."}


def _bos_klasoru_sil(klasor):
    try:
        if os.path.isdir(klasor) and not os.listdir(klasor) and os.path.abspath(klasor).startswith(os.path.abspath(COP)):
            os.rmdir(klasor)
    except Exception:
        pass


def cop_temizle(gun=SAKLAMA_GUN, simdi=None):
    """Süresi dolan çöp öğelerini kalıcı siler. Klasör adı '<unix zamanı>_<rastgele>'. -> silinen öğe sayısı"""
    simdi = simdi or _simdi()
    n = 0
    try:
        for ad in os.listdir(COP):
            try:
                zaman = int(ad.split("_")[0])
            except ValueError:
                continue
            if simdi - zaman > gun * 86400:
                shutil.rmtree(os.path.join(COP, ad), ignore_errors=True)
                n += 1
    except FileNotFoundError:
        pass
    return n


def cop_boyutu():
    toplam = 0
    for kok, _, dosyalar in os.walk(COP):
        for d in dosyalar:
            try:
                toplam += os.path.getsize(os.path.join(kok, d))
            except OSError:
                pass
    return toplam


def _saat(t):
    return time.strftime("%H:%M", time.localtime(t))


def ozet_metni(gun_basi=None, en_fazla=30):
    """'Bugün ne yaptın?' cevabı (yapay zekâ kullanmadan)."""
    if gun_basi is None:
        lt = time.localtime()
        gun_basi = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    bugun = [k for k in oku() if k.get("zaman", 0) >= gun_basi and k.get("tur") != "geri_alma"]
    if not bugun:
        return "Bugün bilgisayarında bir değişiklik yapmadım."
    satirlar = []
    for k in bugun[-en_fazla:]:
        durum = " (geri alındı)" if k.get("geri_alindi") else ("" if k.get("geri") else " (geri alınamaz)")
        satirlar.append(f"{_saat(k['zaman'])} · {TUR_ADI.get(k['tur'], k['tur'])}: {k['ozet']}{durum} [{k['id']}]")
    bas = f"Bugün {len(bugun)} işlem yaptım:" if len(bugun) <= en_fazla else \
        f"Bugün {len(bugun)} işlem yaptım, son {en_fazla} tanesi:"
    return bas + "\n" + "\n".join(satirlar) + ("\n\nBirini geri almak için \"son yaptığını geri al\" ya da "
                                               "\"[numara] geri al\" diyebilirsin.")
