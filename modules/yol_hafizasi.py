# Core: MK-Agentic-System · Powered by FENIX Engine · (c) 2026 Mustafa Koç · GPL-3.0-only (LICENSE, NOTICE.md)
"""Yol hafızası / workflow memory.

FENIX çok adımlı bir işi başarıyla bitirdiğinde izlediği yolu ŞABLON olarak saklar:
    "KocDetailing projesindeki son commit'ler"  ->  "{proje} projesindeki son commit'ler"
    adımlar: mcp_git_git_log(repo_path={proje_yolu}, max_count=10)
Benzer bir istek geldiğinde (başka bir proje için bile) modele "benzer işte şu yolu izledin" ipucu verilir;
model aramaya vakit harcamadan doğrudan doğru araca gider.

Ayrıca bilgisayardaki proje klasörleri (içinde .git olanlar) bir kez taranıp listelenir; "X projesi" denince
klasörün yeri hemen bilinir.

GÜVENLİK: ipucu yalnızca BİLGİDİR, hiçbir şey kendiliğinden çalışmaz; araçların onay kuralları aynen geçerlidir.
Klasör artık yoksa ipucu verilmez. Gizli sohbette hiçbir şey kaydedilmez. Kayıtlar yalnızca bu bilgisayarda
(data/yol_hafizasi.json, data/projeler.json) durur.
Ölçüm: her istekte süre ve araç sayısı data/yol_olcum.jsonl'a yazılır (yol hafızası açık/kapalı karşılaştırması)."""
import datetime
import json
import os
import re
import threading
import uuid

from . import user_settings

YOL_PATH = os.path.join("data", "yol_hafizasi.json")
PROJE_PATH = os.path.join("data", "projeler.json")
OLCUM_PATH = os.path.join("data", "yol_olcum.jsonl")
MAX_YOL = 200
MAX_ADIM = 4
UZUN_ARG = 120                  # bundan uzun metin argümanları (dosya içeriği gibi) şablona girmez
ESIK = 0.6                      # şablon kelimelerinin en az bu kadarı yeni istekte geçmeli
TARAMA_GUN = 1                  # proje listesi en fazla günde bir yeniden taranır

# Bulunan yolu kendisi sağlayan "arama" araçları: yol bilindiğinde gereksizdir, şablona girmez.
KESIF = {"find_files", "list_folder", "open_folder_by_name", "search_web",
         "mcp_dosyalar_search_files", "mcp_dosyalar_list_directory", "mcp_dosyalar_directory_tree",
         "mcp_dosyalar_list_allowed_directories", "mcp_dosyalar_list_directory_with_sizes"}
_ATLA = {"eklentileri_listele", "lab_status", "lab_add_topic", "lab_forget"}

_LOCK = threading.RLock()
_STOP = {"bir", "bu", "şu", "su", "ve", "ile", "için", "icin", "mi", "mı", "mu", "mü", "ne", "neler", "nedir",
         "bana", "benim", "lütfen", "lutfen", "acaba", "şimdi", "simdi", "olan", "gibi", "kadar", "daha"}


# ------------------------------------------------------------------ yardımcılar
def acik():
    return bool(user_settings.get("yol_hafizasi", True))


def fold(t):
    t = (t or "").replace("İ", "i").replace("I", "ı").lower()
    return t.translate(str.maketrans("çğıöşüâîû", "cgiosuaiu"))


def kokler(text):
    """Basit kök kümesi: Türkçe ekler yüzünden kelimenin ilk 5 harfi alınır ('commitlerim' -> 'commi')."""
    out = set()
    for w in re.findall(r"[a-z0-9{}_]+", fold(text)):
        if w in _STOP or len(w) < 3:
            continue
        out.add(w if w.startswith("{") else w[:5])
    return out


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ------------------------------------------------------------------ proje klasörleri
def _kokler_listesi():
    home = os.path.expanduser("~")
    one = os.environ.get("OneDrive", "")
    adaylar = [os.path.join(home, "Desktop"), os.path.join(home, "Documents"), os.path.join(home, "source", "repos"),
               os.path.join(home, "Projects"), os.path.join(home, "Masaüstü"), os.path.join(home, "Belgeler")]
    if one:
        adaylar += [os.path.join(one, "Desktop"), os.path.join(one, "Documents")]
    return [a for a in dict.fromkeys(adaylar) if os.path.isdir(a)]


def projeleri_tara(kokler_=None, derinlik=3):
    """İçinde .git olan klasörleri bulur -> {ad: yol}. node_modules/venv gibi ağır klasörlere girmez."""
    atla = {"node_modules", "venv", ".venv", "__pycache__", ".git", "AppData", "dist", "build", ".idea", ".vscode"}
    bulunan = {}

    def gez(yol, d):
        try:
            girdiler = list(os.scandir(yol))
        except Exception:
            return
        if any(g.name == ".git" for g in girdiler):
            bulunan.setdefault(os.path.basename(yol.rstrip("\\/")), yol)
            return
        if d <= 0:
            return
        for g in girdiler:
            if g.is_dir(follow_symlinks=False) and g.name not in atla and not g.name.startswith("."):
                gez(g.path, d - 1)
    for k in (kokler_ if kokler_ is not None else _kokler_listesi()):
        gez(k, derinlik)
    return bulunan


def projeler():
    return {k: v for k, v in (_load(PROJE_PATH, {}).get("projeler") or {}).items() if os.path.isdir(v)}


def projeleri_guncelle(zorla=False, kokler_=None):
    d = _load(PROJE_PATH, {})
    son = d.get("tarama")
    if not zorla and son:
        try:
            if (datetime.datetime.now() - datetime.datetime.fromisoformat(son)).days < TARAMA_GUN:
                return d.get("projeler") or {}
        except Exception:
            pass
    bulunan = projeleri_tara(kokler_)
    eski = {k: v for k, v in (d.get("projeler") or {}).items() if os.path.isdir(v)}
    eski.update(bulunan)
    with _LOCK:
        _save(PROJE_PATH, {"tarama": datetime.datetime.now().isoformat(timespec="seconds"), "projeler": eski})
    return eski


def proje_ekle(ad, yol):
    if not ad or not os.path.isdir(yol):
        return
    with _LOCK:
        d = _load(PROJE_PATH, {})
        d.setdefault("projeler", {})[ad] = yol
        _save(PROJE_PATH, d)


def projeyi_bul(text, liste=None):
    """Metinde adı geçen bilinen proje -> (ad, yol) ya da None. En uzun eşleşen ad seçilir."""
    liste = projeler() if liste is None else liste
    t = fold(text)
    kelimeler = re.findall(r"[a-z0-9_.-]+", t)
    aday = []
    for ad, yol in liste.items():
        f = fold(ad)
        if len(f) < 3:
            continue
        bitisik = re.sub(r"[\s_.-]+", "", t)            # 'koc detailing' -> 'kocdetailing'
        if f in t or any(w.startswith(f) for w in kelimeler) or \
                (len(f) >= 6 and re.sub(r"[_.-]+", "", f) in bitisik) or \
                (len(f) >= 6 and any(len(w) >= 5 and f.startswith(w) for w in kelimeler)):
            aday.append((len(f), ad, yol))
    if not aday:
        return None
    aday.sort(reverse=True)
    return aday[0][1], aday[0][2]


def _proje_cikar(text, ad, yerine=" "):
    """Metindeki proje adını (ekli ya da boşluklu yazılmış olsa da) 'yerine' ile değiştirir."""
    yeni = re.sub(re.escape(ad), yerine, text, flags=re.I)
    if yeni != text:
        return yeni
    f = fold(ad)
    parcalar = re.findall(r"[a-z0-9]+", f)
    if len(parcalar) == 1 and len(f) >= 6:      # 'kocdetailing' metinde 'koc detailing' diye geçebilir
        for i in range(3, len(f) - 2):
            desen = re.escape(f[:i]) + r"[\s_.-]+" + re.escape(f[i:]) + r"\w*"
            m = re.search(desen, fold(text))
            if m:
                return fold(text)[:m.start()] + yerine + fold(text)[m.end():]
    return re.sub(r"\b\w*" + re.escape(f[:5]) + r"\w*", yerine, fold(text))


# ------------------------------------------------------------------ yolları öğrenme
def _yol_kok(p):
    """Bir dosya/klasör yolunun ait olduğu proje kökü (.git içeren üst klasör) ya da klasörün kendisi."""
    p = os.path.abspath(p)
    d = p if os.path.isdir(p) else os.path.dirname(p)
    cur = d
    for _ in range(6):
        if os.path.isdir(os.path.join(cur, ".git")):
            return cur
        up = os.path.dirname(cur)
        if up == cur:
            break
        cur = up
    return d


def _yol_mu(v):
    return isinstance(v, str) and len(v) > 3 and ("\\" in v or "/" in v) and os.path.exists(v)


def _sablonla(text, calls):
    """(kullanıcı metni, araç çağrıları) -> şablon kaydı ya da None."""
    tamam = [(a, g, s) for a, g, s in calls if a not in _ATLA and isinstance(g, dict)
             and not (isinstance(s, dict) and s.get("status") in ("error", "cancelled"))]
    if not tamam:
        return None
    # proje/klasör yuvası: argümanlardaki gerçek bir yolun proje adı metinde geçiyorsa
    # Önce işi yapan son adımlara bakılır (keşif adımları en sona): "bodrumu listele" adımındaki üst klasör
    # değil, asıl işin yapıldığı proje öğrenilir. .git içeren gerçek proje kökü, düz klasörden önce gelir.
    slot_ad, slot_yol = None, None
    sira = [c for c in reversed(tamam) if c[0] not in KESIF] + [c for c in reversed(tamam) if c[0] in KESIF]
    adaylar = []
    for _, g, _ in sira:
        for v in g.values():
            if _yol_mu(v):
                kok = _yol_kok(v)
                ad = os.path.basename(kok.rstrip("\\/"))
                if ad and projeyi_bul(text, {ad: kok}):
                    adaylar.append((0 if os.path.isdir(os.path.join(kok, ".git")) else 1, ad, kok))
    if adaylar:
        adaylar.sort(key=lambda x: x[0])          # sıralama kararlı: aynı türde ilk bulunan (son adım) kalır
        _, slot_ad, slot_yol = adaylar[0]
    adimlar = []
    yol_var = False
    for a, g, _ in reversed(tamam):              # sondan başa: yol bilindiyse keşif adımları atılır
        if a in KESIF and yol_var:
            continue
        ga = {}
        for k, v in g.items():
            if _yol_mu(v):
                yol_var = True
                tam = os.path.abspath(v)
                if slot_yol and tam.startswith(slot_yol):
                    v = "{proje_yolu}" + tam[len(slot_yol):]
            elif isinstance(v, str) and len(v) > UZUN_ARG:
                v = "<içerik>"                       # yazılan belgenin tamamı yol olarak saklanmaz (04.11)
            ga[k] = v
        adimlar.insert(0, {"arac": a, "arg": ga})
    adimlar = adimlar[-MAX_ADIM:]
    if len(tamam) < 2 and not slot_ad:
        return None                              # tek adımlı, genellenemeyen işler komut hafızasının işi
    kalip = text
    if slot_ad:
        kalip = _proje_cikar(text, slot_ad, "{proje}")
    return {"kalip": kalip.strip()[:300], "adimlar": adimlar, "proje": slot_ad, "adim_sayisi": len(tamam),
            "_proje_yolu": slot_yol}


def ogren(text, calls, incognito=False):
    """Başarılı bir işin yolunu kaydeder. Aynı kalıp varsa sayacını artırır."""
    if incognito or not acik() or not calls:
        return None
    y = _sablonla(text, list(calls))
    if not y:
        return None
    kok = y.pop("_proje_yolu", None)
    if y.get("proje") and kok:
        proje_ekle(y["proje"], kok)          # öğrenilen yer: adı metinde geçen projenin gerçek klasörü
    with _LOCK:
        d = _load(YOL_PATH, [])
        anahtar = json.dumps([s["arac"] for s in y["adimlar"]])
        for e in d:
            if json.dumps([s["arac"] for s in e["adimlar"]]) == anahtar and kokler(e["kalip"]) == kokler(y["kalip"]):
                e["sayac"] = e.get("sayac", 1) + 1
                e["son"] = datetime.datetime.now().isoformat(timespec="seconds")
                e["adimlar"] = y["adimlar"]
                _save(YOL_PATH, d)
                return e
        y.update(id=uuid.uuid4().hex[:8], sayac=1, son=datetime.datetime.now().isoformat(timespec="seconds"))
        d.append(y)
        d = sorted(d, key=lambda e: e.get("son", ""), reverse=True)[:MAX_YOL]
        _save(YOL_PATH, d)
        return y


def yollar():
    return _load(YOL_PATH, [])


def sil(kimlik=None):
    with _LOCK:
        d = [] if kimlik is None else [e for e in yollar() if e.get("id") != kimlik]
        _save(YOL_PATH, d)


# ------------------------------------------------------------------ ipucu
def _benzerlik(istek, kalip):
    a, b = kokler(istek), kokler(kalip) - {"{proje}", "{proj"}
    if not b:
        return 0.0
    return len(a & b) / len(b)


def komsular(yol, en_fazla=15):
    """Bilinen bir klasörün yanındaki (aynı üst klasördeki) klasörler: 'kutunun yanındaki X' için."""
    try:
        ust = os.path.dirname(yol.rstrip("\\/"))
        ad = os.path.basename(yol.rstrip("\\/"))
        out = sorted(d for d in os.listdir(ust) if d != ad and not d.startswith(".")
                     and os.path.isdir(os.path.join(ust, d)))
        return out[:en_fazla]
    except Exception:
        return []


def ipucu(text, liste=None):
    """İsteğe uyan yol varsa modele verilecek kısa metin ve önerilen araç adları -> (metin, {araçlar})."""
    if not acik():
        return "", set()
    liste = projeler() if liste is None else liste
    bulunan = projeyi_bul(text, liste)
    istek = text
    if bulunan:
        istek = _proje_cikar(text, bulunan[0])
    en_iyi, puan = None, 0.0
    for e in yollar():
        if e.get("proje") and not bulunan:
            continue
        p = _benzerlik(istek, e["kalip"])
        if p > puan:
            en_iyi, puan = e, p
    satirlar, araclar = [], set()
    if bulunan:
        satirlar.append(f"Bilinen proje klasörü: {bulunan[0]} → {bulunan[1]}")
        komsu = komsular(bulunan[1])
        if komsu:
            satirlar.append(f"Aynı klasörde ({os.path.dirname(bulunan[1].rstrip(chr(92) + '/'))}) bunlar da var: "
                            + ", ".join(komsu))
    if en_iyi and puan >= ESIK:
        adim_txt = []
        for st in en_iyi["adimlar"]:
            arg = {}
            for k, v in st["arg"].items():
                if isinstance(v, str) and "{proje_yolu}" in v:
                    if not bulunan:
                        break
                    v = v.replace("{proje_yolu}", bulunan[1])
                if isinstance(v, str) and len(v) > UZUN_ARG:
                    v = "<içerik>"
                arg[k] = v
            else:
                adim_txt.append(f"{st['arac']}({json.dumps(arg, ensure_ascii=False)})")
                araclar.add(st["arac"])
        if adim_txt:
            satirlar.append(f"Benzer bir işi ('{en_iyi['kalip'][:80]}') daha önce şu yolla başarıyla yaptın: "
                            + " → ".join(adim_txt) + ". Bu istek de aynı türdense aramaya gerek kalmadan doğrudan "
                            "bu araçları kullan; uymuyorsa bu bilgiyi yok say.")
    if not satirlar:
        return "", set()
    return "[Yol hafızası]\n" + "\n".join(satirlar), araclar


# ------------------------------------------------------------------ ölçüm
def olcum_yaz(text, sure, calls, ipucu_var):
    try:
        os.makedirs(os.path.dirname(OLCUM_PATH), exist_ok=True)
        with open(OLCUM_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.datetime.now().isoformat(timespec="seconds"), "sure": round(sure, 2),
                                "arac_sayisi": len(calls or []), "araclar": [c[0] for c in (calls or [])][:8],
                                "ipucu": bool(ipucu_var), "yol_hafizasi": acik(),
                                "istek": fold(text)[:80]}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def arka_planda_tara():
    threading.Thread(target=lambda: _guvenli(projeleri_guncelle), daemon=True, name="fenix-projeler").start()


def _guvenli(fn):
    try:
        fn()
    except Exception as e:
        print(f"[YOL HAFIZASI] proje taraması: {e}")
